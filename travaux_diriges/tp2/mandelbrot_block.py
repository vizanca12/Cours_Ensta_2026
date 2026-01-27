from mpi4py import MPI
import numpy as np
from dataclasses import dataclass
from PIL import Image
from math import log
from time import time
import matplotlib.cm

# --- CLASSE MANDELBROT ORIGINAL ---
@dataclass
class MandelbrotSet:
    max_iterations: int
    escape_radius:  float = 2.0

    def __contains__(self, c: complex) -> bool:
        return self.stability(c) == 1

    def convergence(self, c: complex, smooth=False, clamp=True) -> float:
        value = self.count_iterations(c, smooth)/self.max_iterations
        return max(0.0, min(value, 1.0)) if clamp else value

    def count_iterations(self, c: complex,  smooth=False) -> int | float:
        if c.real*c.real+c.imag*c.imag < 0.0625:
            return self.max_iterations
        if (c.real+1)*(c.real+1)+c.imag*c.imag < 0.0625:
            return self.max_iterations
        if (c.real > -0.75) and (c.real < 0.5):
            ct = c.real-0.25 + 1.j * c.imag
            ctnrm2 = abs(ct)
            if ctnrm2 < 0.5*(1-ct.real/max(ctnrm2, 1.E-14)):
                return self.max_iterations
        z = 0
        for iter in range(self.max_iterations):
            z = z*z + c
            if abs(z) > self.escape_radius:
                if smooth:
                    return iter + 1 - log(log(abs(z)))/log(2)
                return iter
        return self.max_iterations

# --- PARALELIZAÇÃO ---

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

mandelbrot_set = MandelbrotSet(max_iterations=50, escape_radius=10)
width, height = 1024, 1024
scaleX = 3./width
scaleY = 2.25/height

# 1. Divisão do Trabalho (Blocos de linhas)
lines_per_process = height // size
remainder = height % size

if rank < remainder:
    my_lines = lines_per_process + 1
    start_y = rank * my_lines
else:
    my_lines = lines_per_process
    start_y = rank * my_lines + remainder

end_y = start_y + my_lines

# 2. Cálculo Local
# Matriz local: (width, my_lines)
local_convergence = np.empty((width, my_lines), dtype=np.double)

deb = time()
for y in range(my_lines):
    global_y = start_y + y
    for x in range(width):
        c = complex(-2. + scaleX*x, -1.125 + scaleY * global_y)
        local_convergence[x, y] = mandelbrot_set.convergence(c, smooth=True)
fin = time()

print(f"Processo {rank}: Calculou linhas {start_y} a {end_y} em {fin-deb:.4f}s")

# 3. Rassemblement (Gather) CORRIGIDO
# Primeiro, transpomos localmente para ficar (linhas, colunas) e achatamos.
# Isso garante que enviamos blocos contíguos de linhas.
local_data = local_convergence.T.flatten()

# O mestre precisa saber quantos elementos vêm de cada um
sendcounts = np.array(comm.gather(len(local_data), root=0))

if rank == 0:
    # Buffer plano para receber tudo
    global_data = np.empty(width * height, dtype=np.double)
else:
    global_data = None

# Gatherv recebe em um array plano (1D)
comm.Gatherv(sendbuf=local_data, 
             recvbuf=[global_data, sendcounts, None, MPI.DOUBLE], 
             root=0)

# 4. Reconstrução da Imagem
if rank == 0:
    total_time = time() - deb
    print(f"Tempo Total: {total_time:.4f}s")
    
    # O global_data contém as linhas empilhadas (Transposta da original)
    # Então fazemos reshape para (height, width)
    convergence_T = global_data.reshape((height, width))
    
    # Criação da imagem
    # Como já temos a transposta (linhas x colunas), passamos direto
    image = Image.fromarray(np.uint8(matplotlib.cm.plasma(convergence_T)*255))
    image.save("mandelbrot_block.png")
    print("Imagem salva com sucesso!")