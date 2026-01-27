# Calcul de l'ensemble de Mandelbrot en python (Parallélisé avec MPI)
import numpy as np
from dataclasses import dataclass
from PIL import Image
from math import log
from time import time
import matplotlib.cm
from mpi4py import MPI  # Importação do MPI

@dataclass
class MandelbrotSet:
    max_iterations: int
    escape_radius:  float = 2.0

    def __contains__(self, c: complex) -> bool:
        return self.stability(c) == 1

    def convergence(self, c: np.ndarray, smooth=False, clamp=True) -> np.ndarray:
        value = self.count_iterations(c, smooth)/self.max_iterations
        return np.maximum(0.0, np.minimum(value, 1.0)) if clamp else value

    def count_iterations(self, c: np.ndarray,  smooth=False) -> np.ndarray:
        z:    np.ndarray
        iter: np.ndarray

        # On vérifie dans un premier temps si le complexe
        # n'appartient pas à une zone de convergence connue :
        iter = self.max_iterations * np.ones(c.shape, dtype=np.double)
        mask = (np.abs(c) >= 0.25) | (np.abs(c+1.) >= 0.25)

        # Sinon on itère
        z = np.zeros(c.shape, dtype=np.complex128)
        for it in range(self.max_iterations):
            z[mask] = z[mask]*z[mask] + c[mask]
            has_diverged = np.abs(z) > self.escape_radius
            if has_diverged.size > 0:
                iter[has_diverged] = np.minimum(iter[has_diverged], it)
                mask = mask & ~has_diverged
            if np.any(mask) == False : break
        
        has_diverged = np.abs(z) > 2
        if smooth:
            iter[has_diverged] += 1 - np.log(np.log(np.abs(z[has_diverged])))/log(2)
        return iter

# --- Configuração MPI ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Parâmetros
mandelbrot_set = MandelbrotSet(max_iterations=200, escape_radius=2.)
width, height = 1024, 1024

scaleX = 3./width
scaleY = 2.25/height

# Inicialização da matriz local com ZEROS (importante para o Reduce funcionar)
convergence_local = np.zeros((width, height), dtype=np.double)

# Sincronização antes de começar o tempo
comm.Barrier()
deb = time()

# --- Loop com Distribuição Cíclica (Statique Entrelacée) ---
# Cada processo começa em 'rank' e pula de 'size' em 'size'
for y in range(rank, height, size):
    c = np.array([complex(-2. + scaleX*x, -1.125 + scaleY * y) for x in range(width)])
    convergence_local[:, y] = mandelbrot_set.convergence(c, smooth=True)

# Sincronização e cálculo do tempo de processamento
comm.Barrier()
fin = time()

if rank == 0:
    print(f"Temps du calcul (com {size} processos): {fin-deb:.4f} s")

# --- Reconstituição da Imagem (Apenas no Rank 0) ---
# Prepara a matriz global
convergence_global = None
if rank == 0:
    convergence_global = np.empty((width, height), dtype=np.double)

# Combina (Soma) todas as matrizes locais na global.
# Como as linhas não calculadas são 0.0, a soma reconstrói a imagem perfeitamente.
comm.Reduce(convergence_local, convergence_global, op=MPI.SUM, root=0)

if rank == 0:
    deb_img = time()
    image = Image.fromarray(np.uint8(matplotlib.cm.plasma(convergence_global.T)*255))
    fin_img = time()
    print(f"Temps de constitution de l'image : {fin_img-deb_img:.4f} s")
    image.show()
    # image.save("mandelbrot.png") # Use save se estiver num servidor sem tela