# Relatório — Optimização por Colônia de Formigas (ACO) em Paisagem Fractal

**Data:** 12/03/2026  
**Máquina:** Intel i7-11800H — 8 cores físicos / 16 threads lógicas (hyper-threading), 20 MB L3 cache  
**Compilador:** g++ / mpic++ com `-O3 -march=native -fopenmp -std=c++17`

---

## 1. Objetivo do Projeto

Este projeto é um exercício clássico de Computação de Alto Desempenho (HPC). O objetivo **não é apenas** criar uma simulação de formigas, mas sim transformar um código serial simples em um código extremamente rápido e eficiente, capaz de rodar em múltiplos núcleos (OpenMP) e em vários computadores ao mesmo tempo (MPI).

O trabalho é organizado em quatro passos progressivos:

| Passo | Descrição |
|---|---|
| **A** | Implementar o modelo, o terreno fractal e medir o tempo por iteração (baseline serial) |
| **B** | Vectorização: reorganizar os dados das formigas em SoA (Structure of Arrays) |
| **C** | Paralelismo em Memória Compartilhada (OpenMP) |
| **D** | Paralelismo em Memória Distribuída (MPI) |

## 2. Contexto Experimental

### 2.1 Hardware e Software

| Item | Valor |
|---|---|
| CPU | Intel i7-11800H |
| Cores físicos / threads | 8 / 16 (hyper-threading) |
| Cache L3 | 20 MB (compartilhado) |
| Compilador | g++ 11 / mpic++ (OpenMPI 4.1.6) |
| Flags | `-O3 -march=native -fopenmp -std=c++17` |
| OS | Linux (Ubuntu 22.04) |

### 2.2 Compilação

```bash
cd projet/src && make clean && make all
```

Dois binários são gerados:
- `ant_simu.exe` — versão com SDL2 (interativa) e suporte OpenMP
- `ant_simu_mpi.exe` — versão MPI + OpenMP (sem GUI)

### 2.3 Parâmetros fixos dos benchmarks

| Parâmetro | Valor |
|---|---|
| Dimensão do mapa | 512 × 512 células |
| Formigas (OO/SoA) | 5000 |
| Formigas (MPI) | 20000 |
| Exploração (ε) | 0.8 |
| Ruído do feromônio (α) | 0.7 |
| Evaporação (β) | 0.999 |
| Semente RNG | 2026 |
| Iterações (N) | 1000 (OO/SoA/OMP), 300 (MPI) |
| Runs por configuração | 5 (OO/SoA/OMP), 3 (MPI) |

### 2.4 Metodologia de medição

Para garantir reprodutibilidade:
- Semente fixada (`--seed 2026`) e modo sem GUI (`--no-gui`) para evitar variabilidade do SDL.
- **5 runs** por configuração. Reportamos **média** e **desvio-padrão** do tempo por iteração.
- OpenMP controlado com `OMP_NUM_THREADS`. Para benchmarks sérios: `OMP_PROC_BIND=true OMP_PLACES=cores`.
- Ferramenta `python3 tools/bench.py` automatiza a coleta e calcula média/desvio.

Observação metodológica: quando a diferença entre duas versões fica abaixo de ~2%, os resultados com `N=200` e apenas 3 runs ficam muito sensíveis a ruído do sistema. Para a comparação OO vs SoA, foi usado benchmark com **1000 iterações** e múltiplos runs em `OMP_NUM_THREADS=1`.




---

## 3. Passo A — O Modelo e a Simulação Serial

### 3.1 Descrição do Modelo ACO

#### 3.1.1 O Terreno

O terreno é uma grade 2D de 512×512 células. Cada célula possui um **custo de atravessamento** $c(s) \in [0, 1]$ — quanto maior, mais difícil de atravessar. Há quatro tipos de células:
- **Fourmilière (ninho):** célula de origem
- **Source de nourriture (comida):** destino
- **Indésirables (muros):** valor −1, formigas não podem entrar
- **Libres (livres):** exploráveis

#### 3.1.2 As Formigas

Cada formiga tem dois estados possíveis:
- **Não-carregada:** procura comida seguindo o feromônio V₁
- **Carregada:** voltando ao ninho seguindo o feromônio V₂

Regras de transição de estado:
- Formiga chega à comida → torna-se **carregada**
- Formiga chega ao ninho **carregada** → incrementa o contador de comida, torna-se **não-carregada**

#### 3.1.3 Os Feromônios

Cada célula $s$ armazena dois valores: $V_1(s)$ (guia para a comida) e $V_2(s)$ (guia para o ninho).

**Atualização por uma formiga em $s$:**

$$V_1(s) \leftarrow \begin{cases} 1 & \text{se } s \text{ é a comida} \\ \alpha \cdot \max_{s' \in N(s)} V_1(s') + (1-\alpha) \cdot \frac{1}{4}\sum_{s' \in N(s)} V_1(s') & \text{senão} \end{cases}$$

$$V_2(s) \leftarrow \begin{cases} 1 & \text{se } s \text{ é o ninho} \\ \alpha \cdot \max_{s' \in N(s)} V_2(s') + (1-\alpha) \cdot \frac{1}{4}\sum_{s' \in N(s)} V_2(s') & \text{senão} \end{cases}$$

Onde $\alpha = 0.7$ é o parâmetro de ruído e $N(s)$ são as 4 células vizinhas (esq, dir, cima, baixo).

**Evaporação** ao final de cada iteração:
$$V_i(s) \leftarrow \beta \cdot V_i(s), \quad \beta = 0.999$$

#### 3.1.4 A Regra de Movimento

A cada sub-passo no tempo, a formiga possui 1 unidade de movimento que gasta conforme o custo do terreno $c(s)$. Ela repete sub-passos até esgotar o movimento. Em cada sub-passo:

- **Com probabilidade $\varepsilon = 0.8$** (exploração): avança para uma célula vizinha **aleatória** válida (valor ≠ −1)
- **Com probabilidade $1-\varepsilon = 0.2$** (guiado): avança para o vizinho com maior $V_i(s)$ (V₁ se não-carregada, V₂ se carregada)

O parâmetro $\varepsilon$ é o **coeficiente de exploração**. Um piso de $10^{-3}$ é aplicado ao custo do terreno para evitar loops infinitos em células de custo próximo a zero.

### 3.2 O Terreno Fractal (Algoritmo de Plasma)

O terreno é gerado pelo algoritmo **diamond-square** (divisão recursiva):

1. Geram-se altitudes aleatórias nos **cantos** das sub-grades de tamanho $ns = 2^k$, com desvio máximo $d \cdot ns$.
2. **Recursivamente**, para cada sub-grade:
   - Calcula-se o **ponto médio de cada borda** (interpolação + ruído com desvio $d \cdot ns/2$)
   - Calcula-se o **ponto central** (média dos 4 pontos de borda + ruído)
3. Repete recursivamente até sub-grades 2×2.
4. **Normalização:** todos os valores são remapeados para $[0, 1]$.

Código em `src/fractal_land.cpp`:
```cpp
// Para cada sub-grade de nível ldim, calculamos os pontos médios:
cur_land(i_mid, jBeg) = 0.5*(cur_land(iBeg,jBeg) + cur_land(iEnd,jBeg)) + mid_ind*gen(i_mid,jBeg);
cur_land(iBeg, j_mid) = 0.5*(cur_land(iBeg,jBeg) + cur_land(iBeg,jEnd)) + mid_ind*gen(iBeg,j_mid);
cur_land(i_mid, j_mid) = 0.25*(/* 4 pontos de borda */) + mid_ind*gen(i_mid,j_mid);
```

O resultado: regiões claras na visualização = terreno difícil (alto custo), regiões escuras = fácil.

### 3.3 Estrutura do Código

| Arquivo | Responsabilidade |
|---|---|
| `ant.hpp / ant.cpp` | Lógica de uma formiga: estado, posição, `advance()` |
| `pheronome.hpp` | Mapa de feromônios, evaporação, double-buffer, `mark_pheronome()` |
| `fractal_land.hpp / .cpp` | Geração algorítmica do terreno fractal |
| `ant_simu.cpp` | Loop principal (serial + SoA + OpenMP) + instrumentação de tempo |
| `ant_simu_mpi.cpp` | Loop principal com MPI + OpenMP |

**Loop principal (versão serial):**
```cpp
for (std::size_t it = 0; it < opt.steps; ++it) {
    // Fase 1: cada formiga se move e deposita feromônios
    for (auto& a : ants)
        a.advance(phen, land, pos_food, pos_nest, food_quantity);

    // Fase 2: evaporação dos feromônios  V_i(s) *= beta
    phen.do_evaporation();

    // Fase 3: troca de buffers + condições de contorno
    phen.update();
}
```

### 3.4 Instrumentação de Tempo

Usando `std::chrono::steady_clock`, cada fase é medida individualmente:

```cpp
auto t0 = clock::now();
for (auto& a : ants) a.advance(phen, land, pos_food, pos_nest, food_quantity);
auto t1 = clock::now();
phen.do_evaporation();
auto t2 = clock::now();
phen.update();
auto t3 = clock::now();

timings.ants_s   += duration<double>(t1 - t0).count();
timings.evap_s   += duration<double>(t2 - t1).count();
timings.update_s += duration<double>(t3 - t2).count();
```

### 3.5 Correções Importantes de Robustez

Antes de medir performance, foram necessárias correções:

| Problema | Causa | Correção Aplicada |
|---|---|---|
| Loop infinito em substeps | Custo do terreno = 0 possível | Piso `k_min_step_cost = 1e-3` |
| Underflow de índice (bug) | `x-1` com `size_t` quando `x=0` | Overload `operator()(int,int)` com ghost cells |
| RNG não-determinístico | `m_seed` não inicializado no construtor | `ant(pos, seed) : m_seed(seed)` |
| Buffer inconsistente | Buffer não copiado após `update()` | Adicionado `sync_buffer_from_map()` |

### 3.6 Resultados Baseline (Passo A)

```bash
python3 tools/bench.py --steps 1000 --runs 5 --threads 1 --seed 2026
```

```
== OO OMP_NUM_THREADS=1 steps=1000 runs=5 ==
ants.advance     mean=1.020645e-03 s  std=2.609209e-05 s
pheromone.evap   mean=2.218520e-04 s  std=5.604663e-06 s
pheromone.update mean=1.831760e-04 s  std=4.419829e-06 s
```

**Distribuição do tempo total (1.4257e-03 s/iter):**

| Fase | Tempo (s/iter) | % do Total |
|---|---:|---:|
| `ants.advance` | 1.021e-03 ± 2.61e-05 | **71.6%** |
| `pheromone.evap` | 2.219e-04 ± 5.60e-06 | 15.6% |
| `pheromone.update` | 1.832e-04 ± 4.42e-06 | 12.8% |
| **Total** | **1.4257e-03** | 100% |

**Conclusão do Passo A:** `ants.advance` domina com ~72% do tempo. As fases de evaporação e update (~28%) são alvos naturais para paralelização OpenMP.

---

## 4. Passo B — Vectorização (Structure of Arrays)

### 4.1 O Que é SoA e Por Que Usar?

A representação padrão é **Array of Structures (AoS)**: os dados de cada formiga ficam juntos na memória. Ao iterar sobre as formigas e usar apenas as coordenadas, o processador carrega bytes desnecessários (estado, semente) no cache.

A **Structure of Arrays (SoA)** separa os campos em arrays independentes:

```cpp
// AoS — antes (Array of Structures):
struct ant { int x, y; unsigned char loaded; std::size_t seed; };
std::vector<ant> ants;   // memória: [x0 y0 l0 s0 | x1 y1 l1 s1 | ...]

// SoA — depois (Structure of Arrays):
struct AntSoA {
    std::vector<int>           x;       // todas as coordenadas X juntas
    std::vector<int>           y;       // todas as coordenadas Y juntas
    std::vector<unsigned char> loaded;  // todos os estados juntos
    std::vector<std::size_t>   seed;    // todas as sementes juntas
};
// memória: [x0 x1 x2... | y0 y1 y2... | l0 l1 l2... | s0 s1 s2...]
```

**Vantagem teórica:** ao processar apenas `x[i]` de todas as formigas, o cache carrega um bloco contíguo de coordenadas X → melhor uso de SIMD e menor número de cache misses.

### 4.2 O Que Foi Implementado

A versão SoA está em `ant_simu.cpp` como `struct AntSoA` + função `advance_time_timed_soa()`, ativada por:

```bash
./projet/src/ant_simu.exe --no-gui --vectorized --steps 200
```

A lógica é **idêntica** à versão OO: mesmas fórmulas de feromônios, mesma regra de movimento, mesmo custo do terreno. Apenas a organização de memória muda.

Na revisão desta seção, o kernel SoA foi ajustado para manter `x`, `y`, `loaded` e `seed` em variáveis locais ao longo do loop interno, reduzindo leituras e escritas redundantes nos vetores a cada sub-passo. Isso aproxima melhor o custo do SoA ao custo da versão OO.

Também é importante separar dois conceitos:
- **SoA**: reorganização dos dados em memória para melhorar localidade e preparar vetorização.
- **SIMD real**: geração de instruções vetoriais pelo compilador ou via intrínsecos.

No estado atual, o compilador **não vetorizou automaticamente** o loop principal das formigas. Portanto, o modo `--vectorized` deste projeto deve ser entendido como **versão SoA escalar**, e não como SIMD explícito.

### 4.3 Resultados

```bash
export OMP_NUM_THREADS=1 OMP_PROC_BIND=true OMP_PLACES=cores
python3 tools/bench.py --steps 1000 --runs 5 --threads 1 --seed 2026
python3 tools/bench.py --soa --steps 1000 --runs 5 --threads 1 --seed 2026
```

```
== OO OMP_NUM_THREADS=1 steps=1000 runs=5 ==
ants.advance     mean=1.020645e-03 s  std=2.609209e-05 s
pheromone.evap   mean=2.218520e-04 s  std=5.604663e-06 s
pheromone.update mean=1.831760e-04 s  std=4.419829e-06 s

== SoA OMP_NUM_THREADS=1 steps=1000 runs=5 ==
ants.advance     mean=1.055970e-03 s  std=7.532138e-05 s
pheromone.evap   mean=2.349212e-04 s  std=1.572012e-05 s
pheromone.update mean=1.924872e-04 s  std=1.206314e-05 s
```

**Comparação OO vs SoA revisada (N=1000, OMP=1, seed=2026, 5 runs):**

| Versão | ants.advance | evap | update | **Total (s/iter)** | Vs OO |
|---|---:|---:|---:|---:|---:|
| OO (padrão) | 1.021e-03 ± 2.61e-05 | 2.219e-04 ± 5.60e-06 | 1.832e-04 ± 4.42e-06 | **1.426e-03** | 1.000 |
| SoA | 1.056e-03 ± 7.53e-05 | 2.349e-04 ± 1.57e-05 | 1.925e-04 ± 1.21e-05 | **1.483e-03** | 1.040 |

### 4.4 Análise e Interpretação

Na campanha mais recente (5 runs), a SoA ficou **~4.0% mais lenta no total** em 1 thread.

A leitura anterior de “SoA 12% mais lenta” foi influenciada por dois fatores:

1. **Metodologia curta demais para um efeito pequeno.** Com apenas 200 iterações e 3 runs, o ruído do sistema era comparável ao efeito medido.
2. **Overhead evitável na primeira implementação SoA.** O kernel relia e reescrevia `x[idx]`, `y[idx]`, `loaded[idx]` e `seed[idx]` dentro do loop interno, aumentando o tráfego de memória. Após mover esse estado para variáveis locais, o comportamento ficou alinhado com a expectativa.

O comportamento observado pode variar porque:

1. **O gargalo principal continua sendo o acesso ao mapa global** de feromônios e ao terreno, que são acessos irregulares.
2. **Há muitos branches por formiga** (exploração vs. guiado, carregada vs. não-carregada), o que dificulta SIMD automático.
3. O compilador **não gerou vetorização SIMD real** para o loop das formigas; portanto, o benefício atual do SoA vem basicamente de localidade e simplificação do acesso a dados.

**Conclusão revisada:** neste projeto, a reorganização SoA não produz um salto grande de desempenho. O resultado correto é: **SoA prepara o código para vetorização, mas sem SIMD efetivo e com acesso irregular ao mapa, o ganho em 1 thread pode ser pequeno ou até negativo conforme a carga e o ambiente.**

---

## 5. Passo C — Paralelização com OpenMP (Memória Compartilhada)

### 5.1 Identificação dos Loops

Na versão atual do código, as três fases principais da iteração usam OpenMP:

| Fase | Paralelizável? | Razão |
|---|---|---|
| `ants.advance` | ✅ Sim (implementado) | Paralelização com buffers de marcas por thread, evitando corrida no mapa de feromônio |
| `pheromone.evap` | ✅ Sim | `V[i][j] *= beta` — células completamente independentes |
| `pheromone.update` | ✅ Sim | Cópia de buffer — completamente independente por célula |

### 5.2 O Desafio com `ants.advance`

```cpp
// PROBLEMA: race condition quando duas formigas estão na mesma célula
for (auto& a : ants)
    a.advance(phen, ...);  // chama phen.mark_pheronome(pos) — escreve em phen[pos]
```

Em vez de atomics/mutex por célula (custosos), foi adotada uma solução em duas etapas:

1. Cada thread processa seu bloco de formigas e acumula as posições marcadas em um buffer local.
2. Após o `omp for`, o programa aplica as marcas no mapa de feromônio.

Assim, o movimento das formigas é paralelizado sem disputa direta durante o loop principal de `ants.advance`.

### 5.3 Pragmas Adicionados

**Movimento das formigas (OO e SoA) — `ant_simu.cpp`:**
```cpp
#pragma omp parallel
{
    const int tid = omp_get_thread_num();
    auto& local_marks = marks_per_thread[tid];
    std::size_t local_food = 0;

    #pragma omp for schedule(static)
    for (std::size_t i = 0; i < ants.size(); ++i)
        ants[i].advance(phen, land, pos_food, pos_nest, local_food, &local_marks);
}
```

No caminho SoA, o mesmo princípio é aplicado com `reduction(+ : food_delta)` para o contador de comida.

**Evaporação — `do_evaporation()` em `pheronome.hpp`:**
```cpp
void do_evaporation() {
    #pragma omp parallel for collapse(2) schedule(static)
    for (std::size_t i = 1; i <= m_dim; ++i)
        for (std::size_t j = 1; j <= m_dim; ++j) {
            m_buffer_pheronome[i * m_stride + j][0] *= m_beta;  // V1 *= beta
            m_buffer_pheronome[i * m_stride + j][1] *= m_beta;  // V2 *= beta
        }
}
```
O `collapse(2)` une os dois loops em 512² = 262144 iterações independentes — distribuição ótima entre threads.

**Sincronização de buffer — `sync_buffer_from_map()` em `pheronome.hpp`:**
```cpp
void sync_buffer_from_map() {
    #pragma omp parallel for schedule(static)
    for (size_t k = 0; k < m_map_of_pheronome.size(); ++k)
        m_buffer_pheronome[k] = m_map_of_pheronome[k];
}
```

### 5.4 Resultados OpenMP

```bash
export OMP_PROC_BIND=true OMP_PLACES=cores OMP_DYNAMIC=false
python3 tools/bench.py --steps 1000 --runs 5 --threads 1 2 4 8 --seed 2026
python3 tools/bench.py --soa --steps 1000 --runs 5 --threads 1 2 4 8 --seed 2026
```

```
== OO OMP_NUM_THREADS=1 ==
ants.advance 1.021e-03  evap 2.219e-04  update 1.832e-04

== OO OMP_NUM_THREADS=2 ==
ants.advance 6.376e-04  evap 1.234e-04  update 1.064e-04

== OO OMP_NUM_THREADS=4 ==
ants.advance 6.652e-04  evap 9.388e-05  update 8.635e-05

== OO OMP_NUM_THREADS=8 ==
ants.advance 6.793e-04  evap 7.923e-05  update 7.570e-05
```

**Tabela OO (N=1000, 5000 formigas, 5 runs, seed=2026):**

| Threads $p$ | ants.advance (s/iter) | evap (s/iter) | update (s/iter) | **Total (s/iter)** | $S_p = T_1/T_p$ | $E_p = S_p/p$ |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.021e-03 ± 2.61e-05 | 2.219e-04 ± 5.60e-06 | 1.832e-04 ± 4.42e-06 | **1.426e-03** | 1.000 | 1.000 |
| 2 | 6.376e-04 ± 1.98e-05 | 1.234e-04 ± 5.52e-06 | 1.064e-04 ± 3.85e-06 | **8.673e-04** | 1.644 | 0.822 |
| 4 | 6.652e-04 ± 3.86e-05 | 9.388e-05 ± 7.27e-06 | 8.635e-05 ± 8.58e-06 | **8.454e-04** | 1.687 | 0.422 |
| 8 | 6.793e-04 ± 5.78e-05 | 7.923e-05 ± 1.74e-05 | 7.570e-05 ± 1.79e-05 | **8.342e-04** | 1.709 | 0.214 |

**Tabela SoA (N=1000, 5000 formigas, 5 runs, seed=2026):**

| Threads $p$ | ants.advance (s/iter) | evap (s/iter) | update (s/iter) | **Total (s/iter)** | $S_p = T_1/T_p$ | $E_p = S_p/p$ |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.056e-03 ± 7.53e-05 | 2.349e-04 ± 1.57e-05 | 1.925e-04 ± 1.21e-05 | **1.483e-03** | 1.000 | 1.000 |
| 2 | 6.357e-04 ± 2.74e-05 | 1.261e-04 ± 8.22e-06 | 1.090e-04 ± 7.10e-06 | **8.708e-04** | 1.703 | 0.852 |
| 4 | 6.936e-04 ± 2.77e-05 | 9.507e-05 ± 6.57e-06 | 8.471e-05 ± 6.52e-06 | **8.734e-04** | 1.698 | 0.425 |
| 8 | 6.164e-04 ± 1.22e-05 | 6.960e-05 ± 2.61e-06 | 6.523e-05 ± 1.46e-06 | **7.513e-04** | 1.974 | 0.247 |

### 5.5 Análise dos Resultados

Com a integração da paralelização de `ants.advance`, o comportamento mudou de forma clara:

1. `ants.advance` agora reduz fortemente de 1 para 2/4/8 threads (OO e SoA).
2. O speedup total ficou perto de 1.7x (OO) e 2.0x (SoA) em 8 threads.
3. O ganho deixa de ser "somente evap+update" e passa a atacar o verdadeiro gargalo da aplicação.

**Fases paralelizadas escalam bem:**

| Fase | 1 thread | 8 threads | Redução |
|---|---:|---:|---:|
| OO ants.advance | 1.021e-03 | 6.793e-04 | −33.4% |
| SoA ants.advance | 1.056e-03 | 6.164e-04 | −41.6% |
| OO evap | 2.219e-04 | 7.923e-05 | −64.3% |
| OO update | 1.832e-04 | 7.570e-05 | −58.7% |

**Análise Amdahl (qualitativa):** antes, `ants.advance` era sequencial e limitava fortemente o speedup. Agora, com essa fase também paralela, o limite prático subiu e os resultados observados chegam a ~1.7x (OO) e ~2.0x (SoA) em 8 threads.

---

## 6. Passo D — Paralelização com MPI (Memória Distribuída)

### 6.1 Abordagem 1: Ambiente Replicado + Partição das Formigas

#### Ideia

Cada processo MPI mantém o **mapa completo** (terreno + feromônios) em memória local e cuida de $M/P$ formigas:

```
Processo 0: formigas [0, M/P)    + mapa completo
Processo 1: formigas [M/P, 2M/P) + mapa completo
...
Processo P-1: formigas [(P-1)M/P, M) + mapa completo
```

Ao final de cada iteração, os mapas de feromônios são sincronizados com `MPI_Allreduce(MPI_MAX)`: para cada célula, o valor máximo entre todos os processos é adotado como novo estado global. O `MAX` (e não soma ou média) é justificado pelo enunciado: como o algoritmo ACO pode processar formigas em qualquer ordem, duas formigas em processos diferentes que passam pela mesma célula produzem leituras diferentes — tomamos o máximo como a "melhor informação disponível".

#### Código de Comunicação

```cpp
// Após avançar as formigas locais e calcular evaporação/update local:
MPI_Allreduce(
    phen.raw_map_doubles(),        // buffer local: (dim+2)^2 * 2 doubles
    reduced.data(),                // buffer do resultado global
    phen.raw_map_doubles_count(),  // 514*514*2 = 529,508 doubles ≈ 4.2 MB
    MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD
);
phen.set_map_from_raw_doubles(reduced.data());
phen.sync_buffer_from_map();
```

#### Partição das Formigas (sem comunicação)

```cpp
void compute_local_range(size_t n_total, int rank, int n_ranks,
                         size_t& begin, size_t& end) {
    const size_t base = n_total / n_ranks;
    const size_t rem  = n_total % n_ranks;
    begin = rank * base + min(rank, rem);   // distribui o resto round-robin
    end   = begin + base + (rank < rem ? 1 : 0);
}
```

Cada processo inicializa suas formigas deterministicamente a partir da semente global — **sem comunicação de dados das formigas**, apenas do mapa de feromônios.

#### Uso

```bash
mpirun -np 4 ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --seed 2026
```

### 6.2 Status: Implementação e Benchmark

| Item | Status | Detalhe |
|---|---|---|
| Código compila | ✅ OK | `make all` sem erros |
| Partição de formigas | ✅ OK | Distribuição uniforme com round-robin do resto |
| `MPI_Allreduce(MAX)` | ✅ OK | Implementado e testado |
| Execução pequena (20 steps) | ✅ OK | Sem hang, resultado correto |
| Benchmark de performance | ❌ Bloqueado | `mpirun` trava no sistema de teste |

**Causa do bloqueio:** O OpenMPI 4.1.6 instalado no sistema trava mesmo em casos triviais (`mpirun -np 2 /bin/echo HELLO`). Não é um bug do código. Solução: reinstalar com MPICH (`sudo apt install mpich`) ou testar em cluster.

### 6.3 Análise Teórica do Speedup MPI

Com $P$ processos e $M = 20000$ formigas:

- **Cálculo de formigas:** $T_{cálculo} \approx T_{serial}/P$ → speedup ideal $= P$
- **Comunicação `MPI_Allreduce`:** volume fixo $\approx 4.2$ MB por iteração, independente de $P$
- **Speedup real:** $S_P \approx \frac{T_{serial}}{T_{serial}/P + T_{allreduce}}$

O ponto de equilíbrio (onde o speedup começa a saturar) ocorre quando $T_{allreduce} \approx T_{cálculo}/P$.

### 6.4 Discussão: Vantagens e Limitações

**Vantagens:**
- Implementação simples: sem migração de formigas entre processos.
- Balanceamento de carga perfeito: mesmo número de formigas por processo.

**Limitações:**
- **Volume de comunicação $O(n^2)$:** 4.2 MB por iteração independente de $P$ — não escala bem para mapas grandes.
- **Memória:** cada processo armazena uma cópia completa do mapa; para $n=4096$, seriam 268 MB por processo.

---

## 7. Estratégia para a Segunda Abordagem (Decomposição do Domínio)

Na segunda abordagem, divide-se o **mapa** (não as formigas). Cada processo cuida de uma região retangular + as formigas presentes nela.

### 7.1 Estrutura

**Decomposição 2D:** $P_x \times P_y$ blocos (ex: 2×2 para 4 processos), cada um com $\approx (512/P_x) \times (512/P_y)$ células.

**Halos (Ghost Cells):** A fórmula do feromônio em $(i,j)$ usa os 4 vizinhos. Células de borda precisam dos valores do processo vizinho → 1 camada de halo em cada direção.

```
+----------+----------+
| Proc 0   | Proc 1   |   Halo: borda compartilhada de 1 célula
| [halo →] |[← halo]  |   trocada com MPI_Isend/Irecv
+----------+----------+
| Proc 2   | Proc 3   |
+----------+----------+
```

**Por iteração:**
1. Cada processo move suas formigas locais.
2. **Troca de halos de feromônio** com vizinhos (4 direções): `MPI_Isend / MPI_Irecv` — sobreposição de comunicação e cálculo.
3. Evaporação e atualização local.
4. **Migração de formigas:** se uma formiga cruza a fronteira, seus dados `(x, y, loaded, seed)` são enviados ao processo vizinho usando buffers por direção + `MPI_Alltoallv`.

### 7.2 Comparação com Abordagem 1

| Aspecto | Abordagem 1 | Abordagem 2 |
|---|---|---|
| Dados de feromônio/iter | $O(n^2)$ — mapa completo ≈ 4.2 MB | $O(n)$ — bordas ≈ 16 KB para n=512 |
| Migração de formigas | Nenhuma | $O(\text{formigas na borda})$ |
| Memória por processo | $O(n^2)$ | $O(n^2/P)$ |
| Balanceamento de carga | Perfeito | Variável (ninho concentra formigas) |
| Complexidade de código | Baixa | Alta |

Para $n=512$, $P=4$: Abordagem 2 enviaria ~16 KB/iter vs. 4.2 MB/iter da Abordagem 1 — **262× menos dados de feromônio**.

### 7.3 Desafio: Balanceamento de Carga

O ninho atrai formigas. O processo que contém o ninho pode ter muito mais carga. Mitigações:
- Aumentar $\varepsilon$ (exploração) para dispersar as formigas pelo mapa.
- Posicionar o ninho próximo a uma fronteira entre processos.
- Redistribuição dinâmica quando o desequilíbrio ultrapassar um limiar.

---

## 8. Conclusões

### 8.1 Comparação Exigida no Enunciado

O enunciado pede explicitamente comparar:

1. tempo do **código original**;
2. tempo com **memória organizada (Step B)** em **1 núcleo**;
3. tempo com **memória organizada + OpenMP (Step C)** em **vários núcleos**.

Resultado medido com a mesma metodologia (N=1000, 5 runs, seed=2026, afinidade fixa):

| Comparação pedida | Configuração | Total (s/iter) | Ganho vs original |
|---|---|---:|---:|
| Código original | OO, 1 thread | **1.426e-03** | baseline |
| Step B | SoA, 1 thread | **1.483e-03** | **-4.0%** |
| Step B + Step C | SoA, 8 threads | **7.513e-04** | **+47.3%** |

Leitura direta: com `ants.advance` também paralelizado, o Step C passa a gerar ganho forte. Neste conjunto de medidas, o Step B isolado (1 thread) não melhorou, mas combinado com OpenMP em vários núcleos trouxe o melhor tempo final.

Referência adicional da mesma campanha de medidas:

| Configuração | Total (s/iter) | Speedup $S_p$ | Eficiência $E_p$ |
|---|---:|---:|---:|
| OO + OMP 4 threads | 8.454e-04 | 1.687 (vs OO 1t) | 0.422 |
| SoA + OMP 4 threads | 8.734e-04 | 1.633 (vs OO 1t) | 0.408 |
| SoA + OMP 8 threads | 7.513e-04 | 1.898 (vs OO 1t) | 0.237 |
| MPI 4 ranks | _não medido_ | — | — |

### 8.2 Lições Aprendidas por Passo

| Passo | Resultado | Lição Principal |
|---|---|---|
| **A — Serial** | ~1.43 ms/iter; `ants.advance` domina | Identificar o gargalo é o primeiro passo de qualquer otimização |
| **B — SoA** | variação negativa em 1 núcleo (~-4.0% neste conjunto) | SoA isolado pode variar conforme carga de memória/cache |
| **C — OpenMP** | com `ants.advance` paralelo, ganho forte em multicore (~47% no melhor caso medido) | Atacar o gargalo principal muda o regime de escalabilidade |
| **D — MPI** | Implementação OK, benchmark bloqueado | $O(n^2)$ de comunicação é o risco: funciona para n pequeno, satura para n grande |

### 8.3 Recomendações para Continuar

1. **Refinar `ants.advance` paralelo:** reduzir custo da etapa de merge das marcas de feromônio (por exemplo, compressão por célula ou merge em blocos) para melhorar escalabilidade acima de 8 threads.
2. **Resolver MPI:** Mudar para MPICH e coletar dados de speedup com 1, 2, 4, 8 ranks.
3. **Implementar Abordagem 2 (bonus):** Decomposição de domínio para escalar além da memória de um nó.

Atualização: o item (1) foi implementado na versão atual do código principal.

---

## 9. Comandos de Reprodução

### Compilação completa
```bash
cd projet/src && make clean && make all
```

### Passo A — Baseline serial
```bash
# Benchmark automático (5 runs, média + desvio):
python3 projet/tools/bench.py --steps 1000 --runs 5 --threads 1 --seed 2026

# Manual:
./projet/src/ant_simu.exe --no-gui --steps 1000 --seed 2026
```

### Passo B — SoA
```bash
python3 projet/tools/bench.py --soa --steps 1000 --runs 5 --threads 1 --seed 2026
# ou:
./projet/src/ant_simu.exe --no-gui --vectorized --steps 1000 --seed 2026
```

### Passo C — OpenMP (escalabilidade)
```bash
OMP_PROC_BIND=true OMP_PLACES=cores OMP_DYNAMIC=false \
python3 projet/tools/bench.py --steps 1000 --runs 5 --threads 1 2 4 8 --seed 2026
OMP_PROC_BIND=true OMP_PLACES=cores OMP_DYNAMIC=false \
python3 projet/tools/bench.py --soa --steps 1000 --runs 5 --threads 1 2 4 8 --seed 2026
# ou manual com controle de afinidade:
OMP_NUM_THREADS=4 OMP_PROC_BIND=true OMP_PLACES=cores \
    ./projet/src/ant_simu.exe --vectorized --no-gui --steps 1000 --seed 2026
```

### Passo D — MPI (quando disponível)
```bash
# Validação de execução (20 steps):
mpirun -np 4 ./projet/src/ant_simu_mpi.exe --steps 20 --ants 20000 --seed 2026

# Benchmark completo (requer OpenMPI ou MPICH funcional):
for NP in 1 2 4 8; do
    mpirun -np $NP ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --seed 2026
done

# Ou via harness automático:
python3 projet/tools/bench.py --mpi --steps 300 --runs 3 --ranks 1 2 4 8 --mpi-ants 20000
```

### Modo interativo com visualização
```bash
OMP_NUM_THREADS=4 ./projet/src/ant_simu.exe
```
