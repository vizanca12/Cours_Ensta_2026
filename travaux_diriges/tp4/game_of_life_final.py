"""
Jeu de la vie - Análise de População com Vetorização (Sem Interface Gráfica)
Versão otimizada usando convolve2d da scipy para cálculos vetorizados.
"""
from mpi4py import MPI
import numpy as np
import sys
import time
from scipy.signal import convolve2d

# --- Configuração MPI ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

class Grille:
    def __init__(self, dim, init_pattern=None):
        self.global_dim = dim
        
        if dim[0] % size != 0:
            if rank == 0: print("Erro: A altura deve ser divisível pelo número de processos.")
            sys.exit(1)
            
        self.local_h = dim[0] // size
        self.local_w = dim[1]
        self.local_dim = (self.local_h, self.local_w)
        
        # Inicialização Global (Apenas Rank 0)
        self.global_cells = None
        if rank == 0:
            if init_pattern is not None:
                self.global_cells = np.zeros(dim, dtype=np.uint8)
                indices_i = [v[0] for v in init_pattern]
                indices_j = [v[1] for v in init_pattern]
                self.global_cells[indices_i, indices_j] = 1
            else:
                self.global_cells = np.random.randint(2, size=dim, dtype=np.uint8)

        # Distribuição
        self.cells = np.zeros(self.local_dim, dtype=np.uint8)
        comm.Scatter(self.global_cells, self.cells, root=0)

    @staticmethod        
    def h(x):
        """
        Aplica as regras do jogo de la vida usando operações vetorizadas.
        Entrada: x é a matriz contendo o número de vizinhos vivos de cada célula.
        Saída: Matriz de mudanças a aplicar (combinada com estado atual da célula).
        """
        x[x <= 1] = -1    # Morre por subpopulação
        x[x >= 4] = -1    # Morre por superpopulação
        x[x == 2] = 0     # Mantém estado (para células vivas)
        x[x == 3] = 1     # Nasce ou permanece viva
        return x

    def compute_next_iteration(self):
        """
        Versão vetorizada com MPI usando Ghost Cells (Halo Exchange)
        Aplicação das regras do Game of Life através de convolução.
        """
        # 1. Halo Exchange - Troca de linhas nas bordas
        up_neighbor = (rank - 1) % size
        down_neighbor = (rank + 1) % size
        ghost_top = np.empty(self.local_w, dtype=np.uint8)
        ghost_bottom = np.empty(self.local_w, dtype=np.uint8)
        
        # Trocas não-bloqueantes de linhas fantasmas
        req1 = comm.Isend(self.cells[0, :], dest=up_neighbor, tag=11)
        req2 = comm.Irecv(ghost_bottom, source=down_neighbor, tag=11)
        req3 = comm.Isend(self.cells[-1, :], dest=down_neighbor, tag=22)
        req4 = comm.Irecv(ghost_top, source=up_neighbor, tag=22)
        MPI.Request.Waitall([req1, req2, req3, req4])
        
        # 2. Expandir matriz com ghost cells (simula toro vertical)
        expanded = np.vstack([ghost_top, self.cells, ghost_bottom])
        
        # 3. Convolução para contar vizinhos (otimização vetorizada)
        C = np.ones((3, 3))
        C[1, 1] = 0  # Não contamos a célula central
        voisins = convolve2d(expanded, C, mode='same', boundary='wrap')[1:-1, :]
        
        # 4. Aplicar regras do Game of Life de forma vetorizada
        # Uma célula viva sobrevive com 2 ou 3 vizinhos vivos
        # Uma célula morta nasce com exatamente 3 vizinhos vivos
        next_cells = np.zeros_like(self.cells)
        next_cells[(self.cells == 1) & ((voisins == 2) | (voisins == 3))] = 1
        next_cells[(self.cells == 0) & (voisins == 3)] = 1
        
        self.cells = next_cells

    def get_population_count(self):
        """ 
        Conta células vivas globalmente usando MPI Reduce.
        Realiza uma redução MPI para somar as populações locais.
        """
        # 1. Conta localmente
        local_count = np.sum(self.cells)
        
        # 2. Prepara variável para receber a soma total (apenas no rank 0)
        global_count = np.array(0, dtype='i') if rank == 0 else None
        local_count_arr = np.array(local_count, dtype='i')
        
        # 3. Redução MPI: Soma tudo num passo só
        comm.Reduce(local_count_arr, global_count, op=MPI.SUM, root=0)
        
        return global_count

if __name__ == '__main__':
    # Configuração Padrão
    pattern_name = 'glider_gun'
    if len(sys.argv) > 1: pattern_name = sys.argv[1]
    
    # Dicionário de padrões
    dico_patterns = {
        'glider_gun': ((200,200),[(51,76),(52,74),(52,76),(53,64),(53,65),(53,72),(53,73),(53,86),(53,87),(54,63),(54,67),(54,72),(54,73),(54,86),(54,87),(55,52),(55,53),(55,62),(55,68),(55,72),(55,73),(56,52),(56,53),(56,62),(56,66),(56,68),(56,69),(56,74),(56,76),(57,62),(57,68),(57,76),(58,63),(58,67),(59,64),(59,65)]),
        "acorn"   : ((100,100), [(51,52),(52,54),(53,51),(53,52),(53,55),(53,56),(53,57)]),
        "die_hard" : ((100,100), [(51,57),(52,51),(52,52),(53,52),(53,56),(53,57),(53,58)])
    }

    if pattern_name not in dico_patterns:
        if rank==0: print("Pattern desconhecido. Usando die_hard."); pattern_name="die_hard"
    
    # Inicializa sem PyGame
    grid = Grille(*dico_patterns[pattern_name])

    ITERATIONS = 500
    if rank == 0:
        print(f"--- Iniciando Análise de: {pattern_name} ---")
        print(f"Dimensão: {dico_patterns[pattern_name][0]}")
        print("Iteração | População | Tempo (s)")

    start_time = time.time()
    
    for i in range(ITERATIONS):
        t_iter_start = time.time()
        
        grid.compute_next_iteration()
        pop = grid.get_population_count()
        
        t_iter_end = time.time()
        
        if rank == 0 and i % 10 == 0: # Imprime a cada 10 iterações
            print(f"{i:4d}     | {pop:5d}     | {t_iter_end - t_iter_start:.5f}")

    total_time = time.time() - start_time
    if rank == 0:
        print(f"--- Fim da Simulação ---")
        print(f"Tempo Total para {ITERATIONS} iterações: {total_time:.4f}s")
        print(f"Média por iteração: {total_time/ITERATIONS:.5f}s")
