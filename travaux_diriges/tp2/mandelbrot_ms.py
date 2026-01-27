# mandelbrot_ms.py (Estratégia Mestre-Escravo Corrigida)
import numpy as np
from dataclasses import dataclass
from PIL import Image
from math import log
from time import time
import matplotlib.cm
from mpi4py import MPI
import sys

# --- CLASSE MANDELBROT (Idêntica ao mandelbrot_vec.py para garantir a imagem correta) ---
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

        # 1. Zona de convergência conhecida (otimização inicial)
        iter = self.max_iterations * np.ones(c.shape, dtype=np.double)
        mask = (np.abs(c) >= 0.25) | (np.abs(c+1.) >= 0.25)

        # 2. Iteração vetorizada
        z = np.zeros(c.shape, dtype=np.complex128)
        for it in range(self.max_iterations):
            # Apenas calcula para quem ainda está no conjunto (mask)
            z[mask] = z[mask]*z[mask] + c[mask]
            
            # Verifica quem divergiu agora
            has_diverged = np.abs(z) > self.escape_radius
            
            if has_diverged.size > 0:
                # Atualiza contagem para os que divergiram
                # Nota: precisamos atualizar iter apenas onde mask é True E divergiu
                now_diverged_mask = mask & has_diverged
                iter[now_diverged_mask] = it
                
                # Remove os divergentes da máscara de cálculo
                mask = mask & ~has_diverged
            
            # Se ninguém mais precisar ser calculado, para
            if not np.any(mask): 
                break
        
        # Suavização (Smooth coloring)
        if smooth:
            # Recalcula quem divergiu para aplicar o log
            has_diverged = np.abs(z) > 2
            if np.any(has_diverged):
                iter[has_diverged] += 1 - np.log(np.log(np.abs(z[has_diverged])))/log(2)
        
        return iter

# --- CONFIGURAÇÃO MPI ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
status = MPI.Status()

# Tags para controlar a comunicação
TAG_WORK = 1
TAG_RESULT = 2
TAG_DIE = 3

# --- PARÂMETROS DO PROBLEMA ---
width, height = 1024, 1024
max_iterations = 200
# Escalas idênticas ao original para garantir o enquadramento
scaleX = 3./width
scaleY = 2.25/height

mandelbrot_set = MandelbrotSet(max_iterations=max_iterations, escape_radius=2.)

# --- LÓGICA MESTRE-ESCRAVO ---

if rank == 0:
    # === MESTRE ===
    
    if size < 2:
        print("ERRO: O modo Mestre-Escravo precisa de pelo menos 2 processos (1 Mestre + 1 Escravo).")
        print("Execute com: mpiexec -n 2 (ou mais) python mandelbrot_ms.py")
        sys.exit(1)

    deb = time()
    # Inicializa matriz vazia. Se o cálculo falhar, isso vira "ruído" na imagem.
    convergence = np.empty((width, height), dtype=np.double)
    
    # Lista de todas as linhas (trabalhos) a fazer
    rows_to_compute = list(range(height))
    active_workers = 0
    
    print(f"Mestre iniciado. Distribuindo {height} linhas para {size-1} escravos...")

    # 1. Distribuição Inicial: Enche os escravos com a primeira tarefa
    for worker_rank in range(1, size):
        if rows_to_compute:
            row = rows_to_compute.pop(0)
            comm.send(row, dest=worker_rank, tag=TAG_WORK)
            active_workers += 1
        else:
            comm.send(None, dest=worker_rank, tag=TAG_DIE)

    # 2. Loop de Gestão: Recebe resultado -> Envia nova tarefa
    processed_count = 0
    while active_workers > 0:
        # Recebe (linha, dados) de QUALQUER escravo livre
        data = comm.recv(source=MPI.ANY_SOURCE, tag=TAG_RESULT, status=status)
        source_rank = status.Get_source()
        
        row_idx, row_data = data
        
        # Salva o resultado na coluna correta da matriz
        # Nota: No mandelbrot_vec.py, convergence é (width, height) e preenchemos convergence[:, y]
        convergence[:, row_idx] = row_data
        
        processed_count += 1
        
        # Se ainda tem linha para calcular, manda para este escravo
        if rows_to_compute:
            next_row = rows_to_compute.pop(0)
            comm.send(next_row, dest=source_rank, tag=TAG_WORK)
        else:
            # Sem trabalho? Dispensa o escravo.
            comm.send(None, dest=source_rank, tag=TAG_DIE)
            active_workers -= 1

    fin = time()
    print(f"Cálculo finalizado em {fin-deb:.4f} s.")
    
    # Geração da Imagem (Idêntico ao original)
    deb_img = time()
    # Transposta (.T) é necessária porque o array é (width, height) mas a imagem espera (height, width)
    image = Image.fromarray(np.uint8(matplotlib.cm.plasma(convergence.T)*255))
    fin_img = time()
    print(f"Imagem gerada em {fin_img-deb_img:.4f} s.")
    
    image.save("mandelbrot_ms.png")
    # image.show()

else:
    # === ESCRAVO ===
    while True:
        # Fica esperando ordem do mestre
        row = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
        tag = status.Get_tag()
        
        if tag == TAG_DIE:
            break # Encerra o processo
        
        if tag == TAG_WORK:
            # Calcula a linha solicitada
            y = row
            # Cria o vetor de complexos para esta linha (y fixo, x varia)
            c = np.array([complex(-2. + scaleX*x, -1.125 + scaleY * y) for x in range(width)])
            
            # Executa o cálculo pesado
            row_data = mandelbrot_set.convergence(c, smooth=True)
            
            # Devolve o resultado: (índice da linha, array de dados)
            comm.send((y, row_data), dest=0, tag=TAG_RESULT)