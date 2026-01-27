
from mpi4py import MPI
import numpy as np
from time import time

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

dim = 120

if dim % size != 0:
    if rank == 0: print("Erro: Dimensão não divisível.")
    exit()

# N_loc (Linhas por processo)
N_loc = dim // size

start_row = rank * N_loc
end_row = (rank + 1) * N_loc

# 1. Vetor u completo (Necessário para multiplicar pelas linhas)
u = np.array([(i + 1.0) for i in range(dim)])

# 2. Matriz A Local (Apenas N_loc linhas, todas as colunas)
A_local = np.empty((N_loc, dim), dtype=np.float64)
for i_loc in range(N_loc):
    i_glob = start_row + i_loc
    for j in range(dim):
        A_local[i_loc, j] = (i_glob + j) % dim + 1.0

comm.Barrier()
start_time = time()

# 3. Cálculo parcial
# (N_loc x dim) dot (dim) -> Resultado (N_loc)
v_local_part = np.dot(A_local, u)

# 4. Allgather para montar o vetor final
v_res = np.empty(dim, dtype=np.float64)
# O MPI junta os pedaços v_local_part de cada rank em ordem
comm.Allgather(v_local_part, v_res)

comm.Barrier()
end_time = time()

if rank == 0:
    print(f"v (primeiros 10 elementos) = {v_res[:10]}")
    print(f"Tempo de execução com {size} processos: {end_time - start_time:.6f} s")