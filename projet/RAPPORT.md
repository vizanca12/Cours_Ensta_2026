# Relatório — Optimisation par colonie de fourmis (ACO) em paisagem fractal

Data: 24/02/2026

## 1. Objetivo do projeto
O objetivo é medir e otimizar uma simulação ACO em uma grade 2D com custo de travessia (paisagem fractal), implementando:

1. **Medição de tempo por iteração**, separando as fases do algoritmo.
2. **Vectorização (reorganização de dados)**, trocando uma representação orientada a objetos por uma estrutura “SoA” (Structure of Arrays).
3. **Paralelização em memória compartilhada (OpenMP)** onde for seguro e eficiente.
4. **Paralelização distribuída (MPI)** — *primeira abordagem*: ambiente replicado em todos os processos e partição das formigas.
5. **Estratégia para a segunda abordagem** (decomposição do domínio) — descrição.

## 2. Contexto experimental

### 2.1 Hardware/CPU
Resumo (via `lscpu`):
- CPU: Intel i7‑11800H
- 8 cores físicos / 16 threads lógicas (hyper-threading)

### 2.2 Compilação
O projeto compila em C++17 com otimização e OpenMP habilitado:

- `make -C projet/src all`

O binário interativo usa SDL2 (`ant_simu.exe`). Para benchmarks foi usado o modo sem GUI.

### 2.3 Parâmetros do caso de teste (benchmarks)
Os benchmarks foram executados em modo sem renderização, para medir o custo de computação:

- `./projet/src/ant_simu.exe --no-gui --steps N`

Parâmetros internos atuais (default do código):
- Dimensão do mapa: `512 x 512`
- Número de formigas: `5000` (OpenMP/SoA)
- Exploração: `eps = 0.8`
- Ruído do feromônio: `alpha = 0.7`
- Evaporação: `beta = 0.999`

Para MPI (abordagem 1):
- `ants_total = 20000`
- `steps = 300`

### 2.4 Reprodutibilidade (diretiva de metodologia)

Para que os resultados sejam verificáveis e comparáveis (como pedido na lousa: *duração dos runs, nº de runs, média, desvio-padrão*), a metodologia usada foi:

- Fixar a semente (`--seed 2026`) e executar em modo determinístico (sem GUI) com `--steps N`.
- Executar **vários runs** para cada configuração (ex.: 3 a 10 runs) e reportar **média** e **desvio‑padrão** do tempo por iteração.
- Controlar OpenMP com `OMP_NUM_THREADS` e, quando possível, fixar afinidade (ex.: `OMP_PROC_BIND=true OMP_PLACES=cores`) para reduzir ruído.
- Para MPI, reportar **wall‑time** por iteração (máximo entre ranks) e também o custo de comunicação (`MPI_Allreduce`).

Um harness mínimo foi adicionado para automatizar média/desvio:

- `python3 tools/bench.py --steps 500 --runs 5 --threads 1 2 4 8`
- `python3 tools/bench.py --soa --steps 500 --runs 5 --threads 1`
- `python3 tools/bench.py --mpi --steps 300 --runs 3 --ranks 1 2 4 --mpi-ants 20000`

Modelo de tabela esperado (exemplo de formato):

| Configuração | Métrica | Média (s/iter) | Desvio (s/iter) |
|---|---|---:|---:|
| OMP=1 | ants.advance | … | … |
| OMP=2 | ants.advance | … | … |
| … | … | … | … |

## 3. Instrumentação e correções de robustez

### 3.1 Instrumentação de tempo
Foi adicionada medição com `std::chrono::steady_clock` para as fases:
- `ants.advance`: movimento + depósito de feromônios pelas formigas
- `pheromone.evap`: evaporação
- `pheromone.update`: troca de buffers e aplicação de condições de contorno
- (modo interativo) `render`

A saída imprime tempos totais e **médios por iteração**.

### 3.2 Correções importantes encontradas durante a análise
Foram necessárias correções para garantir reprodutibilidade e evitar UB (undefined behavior):

1. **Seed da formiga não inicializado**: o construtor recebia `seed`, mas `m_seed` não era inicializado; isso tornava o RNG não-determinístico e incorreto.
2. **Acesso fora de faixa nos vizinhos do feromônio**: quando `x=0`/`y=0`, acessos do tipo `x-1` em índices `size_t` geravam underflow. Foi adicionado um overload `operator()(int,int)` em `pheronome` para endereçar corretamente as “ghost cells”.
3. **Consistência do double-buffer do feromônio**: após `update()`, o buffer usado no passo seguinte precisa refletir o estado atual do mapa. Foi criado `sync_buffer_from_map()`.

Essas correções são essenciais antes de comparar performance, pois evitam “crashes silenciosos” e resultados inconsistentes.

## 4. Vectorização (reorganização de dados)

### 4.1 O que foi feito
Foi implementado um modo de benchmark com **SoA (Structure of Arrays)**, ativado por:

- `./projet/src/ant_simu.exe --no-gui --vectorized --steps N`

Em vez de `std::vector<ant>`, a simulação usa quatro vetores paralelos:
- `x[i]`, `y[i]` (posição)
- `loaded[i]` (estado carregada/não carregada)
- `seed[i]` (RNG por formiga)

A lógica foi mantida equivalente (mesmos testes de vizinhança, escolha exploratória vs. guiada por feromônio, custo do terreno, etc.).

### 4.2 Resultados
Benchmarks com `N = 1000` iterações, `OMP_NUM_THREADS=1`:

| Versão | ants.advance (s/iter) | evap (s/iter) | update (s/iter) | Total (s/iter) | Razão vs OO |
|---|---:|---:|---:|---:|---:|
| OO (padrão) | 0.000840515 | 0.000229563 | 0.000184138 | 0.001254216 | 1.000 |
| SoA | 0.000864654 | 0.000231305 | 0.000186589 | 0.001282548 | 1.0226 |

**Interpretação:** nesta implementação, SoA ficou ~2.3% mais lenta no total. Isso pode acontecer porque:
- o custo é dominado por acessos indiretos no mapa de feromônios/terreno (pouco “streaming” linear);
- a lógica de decisão por formiga tem muitos branches e leituras dispersas;
- a versão OO já é relativamente compacta e otimizada por `-O3 -march=native`.

Mesmo assim, a versão SoA é útil como base para paralelização mais fina e para reduzir overhead de objetos caso o modelo seja estendido.

### 4.3 Medidas com média e desvio (bench.py)

Para cumprir a diretiva de metodologia (*vários runs + média + desvio-padrão*), foi executado:

- `python3 tools/bench.py --soa --steps 200 --runs 5 --threads 1`

Resumo (tempo total por iteração):

| Versão | Total mean (s/iter) | Total std (aprox) | Razão vs OO (OMP=1) |
|---|---:|---:|---:|
| SoA (OMP=1) | 1.327546e-03 | 3.686766e-05 | 1.0234 |

Nota: o desvio do total é uma aproximação $\sigma_{total}\approx\sqrt{\sum \sigma_i^2}$.

## 5. Paralelização em memória compartilhada (OpenMP)

### 5.1 O que pode e o que não pode paralelizar diretamente
A fase `ants.advance` **não** foi paralelizada “naive” porque cada formiga chama `phen.mark_pheronome()` e escreve no mesmo buffer de feromônios, criando **condições de corrida**.

Nesta etapa, foram paralelizadas apenas as partes **seguras e independentes**:
- evaporação do feromônio (`do_evaporation`) com `collapse(2)`;
- cópia/sincronização do buffer após atualização do mapa (`sync_buffer_from_map`).

### 5.2 Resultados OpenMP
Benchmarks com `N=1000` iterações e 5000 formigas:

| Threads | ants.advance (s/iter) | evap (s/iter) | update (s/iter) | Total (s/iter) | Speedup | Eficiência |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.000840515 | 0.000229563 | 0.000184138 | 0.001254216 | 1.000 | 1.000 |
| 2 | 0.000875006 | 0.000125303 | 0.000104415 | 0.001104724 | 1.135 | 0.568 |
| 4 | 0.000848467 | 0.0000769925 | 0.000065251 | 0.000990711 | 1.266 | 0.316 |
| 8 | 0.00102687 | 0.000102837 | 0.0000860585 | 0.001215766 | 1.032 | 0.129 |

Cálculos:
- Speedup: $S_p = T_1 / T_p$
- Eficiência: $E_p = S_p / p$

**Interpretação:**
- Há ganho até 4 threads, mas **limitado** (Lei de Amdahl), pois `ants.advance` permanece sequencial e domina o tempo.
- Em 8 threads há piora: overhead de criação/sincronização e hyper-threading competindo por recursos de memória.

### 5.3 Medidas com média e desvio (bench.py)

Foi executado:

- `python3 tools/bench.py --steps 200 --runs 5 --threads 1 2 4 8`

Tempos por iteração (média ± desvio):

| Threads | ants.advance (s) | evap (s) | update (s) |
|---:|---:|---:|---:|
| 1 | 8.718454e-04 ± 3.746029e-05 | 2.369664e-04 ± 1.052158e-05 | 1.883576e-04 ± 8.487508e-06 |
| 2 | 8.477570e-04 ± 4.175414e-05 | 1.214322e-04 ± 4.426329e-06 | 1.003739e-04 ± 2.587894e-06 |
| 4 | 8.447790e-04 ± 2.005311e-05 | 7.793362e-05 ± 4.288983e-06 | 6.357790e-05 ± 4.835975e-06 |
| 8 | 9.250100e-04 ± 4.467930e-05 | 6.103536e-05 ± 4.487693e-06 | 5.114740e-05 ± 1.517008e-06 |

Tempo total por iteração (soma das fases) e speedup (calculados a partir das médias):

| Threads | Total mean (s/iter) | Total std (aprox) | Speedup | Eficiência |
|---:|---:|---:|---:|---:|
| 1 | 1.297169e-03 | 3.982480e-05 | 1.000 | 1.000 |
| 2 | 1.069563e-03 | 4.206778e-05 | 1.2128 | 0.6064 |
| 4 | 9.862905e-04 | 2.106915e-05 | 1.3152 | 0.3288 |
| 8 | 1.037193e-03 | 4.492973e-05 | 1.2507 | 0.1563 |

Nota: o desvio do total é uma aproximação $\sigma_{total}\approx\sqrt{\sum \sigma_i^2}$.

## 6. Paralelização MPI — Primeira abordagem (implementada)

### 6.1 Ideia
Cada processo MPI mantém **o ambiente completo** (terreno + mapas de feromônio) e simula **apenas um subconjunto de formigas**. Ao final de cada iteração, os processos combinam os feromônios calculados com:

- `MPI_Allreduce(..., MPI_MAX)`

Ou seja, para cada célula e tipo de feromônio, toma-se o **máximo global** entre processos (conforme sugerido no enunciado para resolver discrepâncias de ordem de atualização entre processos).

### 6.2 Implementação
Executável: `./projet/src/ant_simu_mpi.exe`

Uso (exemplo):
- `mpirun -np 4 ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --omp-threads 1`

Notas:
- A inicialização das formigas é determinística por índice global (`seed + idx * const`), então não é necessário `Scatter`.
- Para evitar oversubscription, por padrão usa-se `--omp-threads 1` (o OpenMP interno é opcional em MPI).

### 6.3 Resultados
Benchmarks com `ants_total=20000`, `steps=300`, `--omp-threads 1`.

Tempo de parede (wall-time) por iteração (**máximo entre ranks**, medido com `MPI_Wtime` + `MPI_Reduce(MPI_MAX)`):

| MPI ranks | Wall-time (s/iter) | Speedup | Eficiência |
|---:|---:|---:|---:|
| 1 | 0.00477276 | 1.000 | 1.000 |
| 2 | 0.00500832 | 0.953 | 0.476 |
| 4 | 0.00796819 | 0.599 | 0.150 |

Tempos médios por iteração por fase (média por rank):

| MPI ranks | ants.advance | evap | update | Allreduce(MAX) | Total |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.00387819 | 0.000302759 | 0.000002407 | 0.000588861 | 0.004772217 |
| 2 | 0.00272700 | 0.000408693 | 0.000003260 | 0.001867990 | 0.005006943 |
| 4 | 0.00200419 | 0.000672872 | 0.000006984 | 0.005280840 | 0.007964886 |

**Interpretação:**
- O custo de `ants.advance` cai com mais ranks (menos formigas por processo), como esperado.
- Porém, `MPI_Allreduce(MAX)` cresce rapidamente e **domina** o tempo total.
- Resultado: **não há aceleração** para estes parâmetros; a comunicação é o gargalo.

Observação: esta é uma conclusão válida e esperada para a abordagem 1 quando o mapa é grande (muitas células) e o merge acontece a cada iteração.

### 6.4 Medidas com média e desvio (bench.py)

Para obter média e desvio (vários runs), foi executado:

- `python3 tools/bench.py --mpi --steps 100 --runs 3 --ranks 1 2 4 --mpi-ants 20000 --omp-threads 1`

Resultados por iteração (média ± desvio), **média por rank**:

| Ranks | ants.advance (s) | evap (s) | update (s) | Allreduce(MAX) (s) | Total mean (s/iter) | Total std (aprox) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.895310e-03 ± 1.372120e-04 | 3.130020e-04 ± 1.506781e-05 | 2.778633e-06 ± 1.172763e-07 | 5.810033e-04 ± 1.972733e-05 | 4.792094e-03 | 1.394394e-04 |
| 2 | 2.705987e-03 ± 1.312744e-05 | 4.098400e-04 ± 2.966733e-06 | 3.301780e-06 ± 1.387112e-07 | 1.862777e-03 ± 6.138385e-05 | 4.981906e-03 | 6.284208e-05 |
| 4 | 2.048167e-03 ± 5.045546e-05 | 6.675913e-04 ± 1.631959e-05 | 7.270517e-06 ± 2.182967e-07 | 5.357527e-03 ± 8.345277e-05 | 8.080556e-03 | 9.887616e-05 |

Speedup aproximado (usando o total médio por rank como proxy de custo; para wall-time real ver a seção 6.3):

| Ranks | Speedup | Eficiência |
|---:|---:|---:|
| 1 | 1.000 | 1.000 |
| 2 | 0.9619 | 0.4809 |
| 4 | 0.5930 | 0.1483 |

Nota: o desvio do total é uma aproximação $\sigma_{total}\approx\sqrt{\sum \sigma_i^2}$.

## 7. Estratégia proposta — Segunda abordagem (decomposição do domínio)

Na segunda abordagem, cada processo mantém apenas um **subdomínio** do mapa (bloco 2D), incluindo uma camada de halos (ghost cells). A estratégia recomendada é:

1. **Decomposição 2D do mapa**: dividir o domínio em blocos (Px × Py) para reduzir a área de halo por processo.
2. **Halos de feromônio**:
   - a atualização `mark_pheronome()` precisa das 4 vizinhanças; portanto, cada iteração requer troca de halos de 1 célula (bordas) com vizinhos.
   - usar `MPI_Isend/Irecv` para sobrepor comunicação e cálculo.
3. **Migração de formigas**:
   - após mover uma formiga, se ela sair do subdomínio, empacotar seus dados (x,y,estado,seed) e enviar ao processo vizinho correspondente.
   - usar buffers por direção (N/S/E/W) e um `MPI_Alltoallv` (ou envios ponto-a-ponto) por iteração.
4. **Balanceamento de carga**:
   - o processo do ninho pode concentrar formigas. Mitigações:
     - aumentar `eps` (exploração) para dispersão;
     - usar decomposição que coloque o ninho próximo a uma fronteira (distribui mais cedo);
     - (avançado) redistribuição dinâmica de subdomínios.
5. **Cálculo local + evaporação local**:
   - evaporação e update do feromônio são locais; somente halos precisam comunicação.

**Por que essa abordagem pode escalar melhor?**
- Troca apenas *bordas* (O(n)) em vez do mapa inteiro (O(n²)).
- Migração de formigas tende a ser pequena por iteração quando a exploração não é extrema.

## 8. Conclusões

- A instrumentação mostrou que o tempo por iteração é dominado por `ants.advance` no caso OpenMP, e por `Allreduce` no caso MPI.
- A reorganização SoA (vectorização) não trouxe ganho para este kernel específico (acessos dispersos e branches dominantes).
- O OpenMP foi efetivo em partes independentes (evaporação + sync), com speedup máximo observado ~1.27× em 4 threads.
- A abordagem MPI 1 (mapa replicado + `Allreduce(MAX)` por iteração) é simples e correta, mas tem **alto custo de comunicação**, e pode não acelerar dependendo de tamanho do mapa e frequência de merge.
- A abordagem MPI 2 (decomposição do domínio + halos + migração de formigas) é a estratégia recomendada para reduzir comunicação e escalar melhor.

## 9. Comandos usados (reprodutibilidade)

### OpenMP
- `make -C projet/src all`
- `OMP_NUM_THREADS=1 ./projet/src/ant_simu.exe --no-gui --steps 1000`
- `OMP_NUM_THREADS=2 ./projet/src/ant_simu.exe --no-gui --steps 1000`
- `OMP_NUM_THREADS=4 ./projet/src/ant_simu.exe --no-gui --steps 1000`
- `OMP_NUM_THREADS=8 ./projet/src/ant_simu.exe --no-gui --steps 1000`

### Vectorizado (SoA)
- `OMP_NUM_THREADS=1 ./projet/src/ant_simu.exe --no-gui --vectorized --steps 1000`

### MPI (abordagem 1)
- `mpirun -np 1 ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --omp-threads 1`
- `mpirun -np 2 ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --omp-threads 1`
- `mpirun -np 4 ./projet/src/ant_simu_mpi.exe --steps 300 --ants 20000 --omp-threads 1`
