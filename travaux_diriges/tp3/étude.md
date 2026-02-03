# Guia de Estudo: Algoritmos de Ordenação Paralela

## 1. Fundamentos 
A ordenação paralela não é apenas sobre comparar números, mas sobre gerenciar a comunicação entre processos 

* Complexidade de Comunicação: Em sistemas distribuídos, trocar dados é muito caro. O tempo total é influenciado pela latência ($t_s$) e pela taxa de transferência ($t_d$).

* Limites Teóricos: O melhor algoritmo sequencial tem complexidade média de $O(n \log n)$. Com $n$ processadores, o speed-up ideal esperado é de $O(\log n)$, embora difícil de alcançar na prática .

* Granularidade: Nem sempre usar mais processos é melhor; muitas vezes, o custo de coordenação supera o ganho de velocidade.

## 2. Algoritimos de troca direta 
**Rank Sort (O "Ideal" Teórico)**
* Lógica: Conta quantos números são menores que um elemento $a$. Esse total define a posição final de $a$ 
* Paralelismo: Com $n$ processos, a complexidade cai para $O(n)$. Usando uma estrutura de árvore com $n^2$ processos, pode chegar a $O(\log_2 n)$.

**Odd-Even Sort (Bubble Sort Paralelo)**
* Fase Par: Processos de rank par comparam/trocam com o vizinho à direita ($rank+1$) .
* Fase Ímpar: Processos mudam o par de comunicação para garantir a circulação dos dados 
* Versão por Bloco: Cada processo ordena sua lista local e usa um algoritmo de fusão (merge sort) para trocar e manter apenas a metade (superior ou inferior) que lhe cabe .

## 3. Ordenação 2D: ShareSort
Utiliza uma grade bidimensional para organizar os dados no estilo snake-like (cobra)
* Fase de Linha: Linhas pares ordenam de forma crescente; linhas ímpares de forma decrescente.
* Fase de Coluna: Todas as colunas ordenam de forma crescente (topo para baixo).
* Duração: O array estará totalmente ordenado após $\log_2(N) + 1$ fases. 

## 4. Hyperquicksort
Uma evolução do Quicksort para arquiteturas de hipercubo.
* Pivotagem: O sucesso depende da escolha do pivô (idealmente a mediana) para manter o equilíbrio de carga.
* Comunicação: Pares de processos trocam dados baseados em sua distância no hipercubo (um bit de diferença no rank binário) .

## 5 Bucket Sort 
O Bucket Sort Paralelo é um dos algoritmos mais eficientes para sistemas distribuídos quando se conhece a distribuição dos dados, pois ele permite que cada processo trabalhe de forma quase totalmente independente após a fase inicial de troca.

### 1. Conceito funcadmental 
Diferente de algoritmos baseados em comparações diretas entre todos os elementos (como o Bubble Sort), o Bucket Sort utiliza uma estratégia de particionamento por valor

* O domínio total dos dados (ex: de 0 a 1000) é dividido em intervalos chamados "baldes"
* Na versão paralela, cada processo do sistema atua como um balde individual

### 2. O desafio: COmo escolher os intervalos?
Este é o ponto mais crítico. Se os intervalos forem fixos e mal distribuídos, um processo pode acabar com 90% dos dados enquanto os outros ficam ociosos (o chamado load imbalance ou desequilíbrio de carga).

Para evitar isso, o algoritmo utiliza uma amostragem inteligente para calcular os intervalos (pivôs) dinamicamente:

* Ordenação Local Prévia: Cada processo ordena seus próprios dados iniciais.
* Seleção de Amostras: Cada processo escolhe $nbp+1$ valores em intervalos regulares de sua lista já ordenada.
* Cálculo Global: Essas amostras são reunidas (Gather) em um array central.
* Definição dos Divisores (Splitters): Esse array é ordenado e novos $nbp+1$ valores são extraídos para definir os limites finais dos baldes de cada processo

### 3. Fase do Algoritmo Paralelo 

#### Fase A: Distribuição Local e Troca (Scatter)
Uma vez que cada processo conhece o seu intervalo de reponsabilidade: 
* Cada processo analisa sua sublista original e separa os elementos que pertencem aos intervalos dos outros processos
* Ocorre uma troca de dados (All-to-All Exchange). O custo dessa comunicação é dado por $(nbp-1)(t_{s} + \frac{N}{nbp^{2}}t_{d})$, onde $t_s$ é a latência e $t_d$ a taxa de transferência.

#### Fase B: Ordenação Local Final 
* Após a troca, cada processo agora possui apenas dados que "caíram" no seu balde.
* Uma ordenação final é realizada localmente, geralmente usando um algoritmo de fusão (fusion sort), com complexidade de $2(nbp-1)\frac{N}{nbp}$.

#### Função C: Reunião (Gather)
* Como o Processo $P_0$ tem o menor intervalo, o $P_1$ o seguinte, e assim por diante, a lista global final já está ordenada pela simples concatenação dos resultados de cada processo.

### 4 Implementação
Quando você for codificar, lembre-se destes pontos práticos mencionados no curso:
* Gestão de Memória: O processo receptor não sabe de antemão quantos dados receberá. Você precisará usar um MPI_Probe para verificar o tamanho da mensagem, alocar um buffer dinâmico e só então realizar o MPI_Recv.
* Minimização de Trocas: Como a troca de dados é a parte mais cara, agrupar todos os elementos que vão para o mesmo processo em um único pacote é essencial para reduzir o impacto da latência ($t_s$).