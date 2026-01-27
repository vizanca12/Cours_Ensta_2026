
from mpi4py import MPI
import numpy as np
from time import time

# Inicialização MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Dimensão do problema
dim = 120

# Verificação de divisibilidade
if dim % size != 0:
    if rank == 0:
        print("Erro: A dimensão deve ser divisível pelo número de processos.")
    exit()

# Cálculo de N_loc (Colunas por processo)
N_loc = dim // size

# Definição dos índices globais para este processo
# Colunas de start_col até end_col (exclusivo)
start_col = rank * N_loc
end_col = (rank + 1) * N_loc

# 1. Criação do vetor u local (apenas a parte que cabe a este processo)
# u[j] = j + 1
u_local = np.array([(j + 1.0) for j in range(start_col, end_col)])

# 2. Criação da Matriz A local (Todas as linhas, mas apenas N_loc colunas)
# Aij = (i+j) % dim + 1
A_local = np.empty((dim, N_loc), dtype=np.float64)
for i in range(dim): # i = linha global
    for j_loc in range(N_loc): # j_loc = índice local da coluna
        j_glob = start_col + j_loc
        A_local[i, j_loc] = (i + j_glob) % dim + 1.0

# Barreiras para sincronizar o tempo
comm.Barrier()
start_time = time()

# 3. Cálculo do produto parcial
# (dim x N_loc) dot (N_loc) -> Resultado (dim)
v_partial = np.dot(A_local, u_local)

# 4. Redução (Soma) para obter o vetor completo em todos os processos
v_res = np.zeros(dim, dtype=np.float64)
comm.Allreduce(v_partial, v_res, op=MPI.SUM)

comm.Barrier()
end_time = time()

if rank == 0:
    print(f"v (primeiros 10 elementos) = {v_res[:10]}")
    print(f"Tempo de execução com {size} processos: {end_time - start_time:.6f} s")