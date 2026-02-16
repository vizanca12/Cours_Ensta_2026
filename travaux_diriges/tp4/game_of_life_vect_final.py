"""
Jeu de la vie - Version Parallèle MPI
Baseado no código original do usuário, adaptado para decomposição de domínio.
"""
from mpi4py import MPI
import pygame as pg
import numpy as np
import sys
import time
from scipy.signal import convolve2d

# --- Configuração MPI ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

class Grille:
    def __init__(self, dim, init_pattern=None, color_life=pg.Color("black"), color_dead=pg.Color("white")):
        self.global_dim = dim
        self.col_life = color_life
        self.col_dead = color_dead
        
        # 1. Decomposição de Domínio
        if dim[0] % size != 0:
            if rank == 0: print("Erro: A altura deve ser divisível pelo número de processos.")
            sys.exit(1)
            
        self.local_h = dim[0] // size
        self.local_w = dim[1]
        self.local_dim = (self.local_h, self.local_w)
        
        # 2. Inicialização Global (Apenas no Rank 0)
        self.global_cells = None # Garante que existe em todos os ranks
        if rank == 0:
            if init_pattern is not None:
                self.global_cells = np.zeros(dim, dtype=np.uint8)
                indices_i = [v[0] for v in init_pattern]
                indices_j = [v[1] for v in init_pattern]
                self.global_cells[indices_i, indices_j] = 1
            else:
                self.global_cells = np.random.randint(2, size=dim, dtype=np.uint8)

        # 3. Distribuição (Scatter)
        # Prepara o buffer local
        self.cells = np.zeros(self.local_dim, dtype=np.uint8)
        
        # CORREÇÃO AQUI: Passamos a matriz inteira. O Scatter divide sozinho.
        # Sendbuf: (buffer, count, type) ou apenas buffer se for divisão igual
        # O mpi4py divide o primeiro eixo (linhas) automaticamente.
        comm.Scatter(self.global_cells, self.cells, root=0)

    @staticmethod        
    def h(x):
        # Regras do jogo aplicadas ao resultado da convolução
        # x é a matriz de vizinhos
        x[x<=1] = -1  # Morre por subpopulação (nota: seu código original usava lógica diferente aqui, mantive a ideia)
        x[x>=4] = -1  # Morre por superpopulação
        x[x==2] = 0   # Mantém estado
        x[x==3] = 1   # Nasce
        return x

    def compute_next_iteration(self):
        """
        Versão MPI com Ghost Cells
        """
        # --- PASSO 1: Troca de Ghost Cells (Halo Exchange) ---
        # Vizinhos no anel (Toro Vertical)
        up_neighbor = (rank - 1) % size
        down_neighbor = (rank + 1) % size
        
        # Buffers para receber as bordas fantasmas
        ghost_top = np.empty(self.local_w, dtype=np.uint8)
        ghost_bottom = np.empty(self.local_w, dtype=np.uint8)
        
        # Envia minha linha de CIMA (índice 0), Recebe linha de BAIXO do vizinho de CIMA
        # (Espera... Se eu sou Rank 1, meu vizinho de cima é 0. 
        # Eu envio meu topo pra ele. Ele me envia o fundo dele, que vira meu fantasma superior)
        
        req1 = comm.Isend(self.cells[0, :], dest=up_neighbor, tag=11)
        req2 = comm.Irecv(ghost_bottom, source=down_neighbor, tag=11)
        req3 = comm.Isend(self.cells[-1, :], dest=down_neighbor, tag=22)
        req4 = comm.Irecv(ghost_top, source=up_neighbor, tag=22)
        
        MPI.Request.Waitall([req1, req2, req3, req4])
        
        # --- PASSO 2: Construir Matriz Expandida (com Ghost Cells) ---
        # Matriz local + 2 linhas (uma em cima, uma em baixo)
        expanded_cells = np.vstack([ghost_top, self.cells, ghost_bottom])
        
        # --- PASSO 3: Cálculo (Convolução) ---
        C = np.ones((3,3))
        C[1,1] = 0
        
        # Truque: Usamos 'boundary=wrap' APENAS para as laterais (Toro Horizontal).
        # Para o vertical, já temos as ghost cells, então não precisamos que o convolve2d faça wrap vertical.
        # Mas o convolve2d faz wrap em ambos ou nenhum. 
        # Solução: Como já temos ghost cells verticais, usamos boundary='wrap'. 
        # O wrap vertical será redundante (vai pegar a ghost cell e jogar pro outro lado), mas o 'mode=valid' vai cortar isso fora.
        
        voisins = convolve2d(expanded_cells, C, mode='valid', boundary='wrap')
        
        # O 'mode=valid' com kernel 3x3 reduz a dimensão em 2 linhas e 2 colunas.
        # Como adicionamos 2 linhas (ghosts), a altura volta ao normal (local_h).
        # Porém, a largura perdeu 2 colunas porque não adicionamos ghosts laterais (confiamos no wrap).
        # ERRO COMUM: convolve2d com 'valid' não faz wrap horizontal.
        # CORREÇÃO: Vamos usar 'same' na matriz expandida e depois cortar o meio.
        
        voisins = convolve2d(expanded_cells, C, mode='same', boundary='wrap')
        
        # Cortar as ghost cells (primeira e última linha) para voltar ao tamanho local
        voisins = voisins[1:-1, :]
        
        # Aplicar regras
        # Lógica vetorial otimizada
        # Célula viva (1) continua viva se tiver 2 ou 3 vizinhos
        # Célula morta (0) nasce se tiver 3 vizinhos
        next_cells = np.zeros(self.cells.shape, dtype=np.uint8)
        next_cells[(self.cells == 1) & ((voisins == 2) | (voisins == 3))] = 1
        next_cells[(self.cells == 0) & (voisins == 3)] = 1
        
        self.cells = next_cells
        return [] # diff_cells não usado aqui

    def get_global_grid(self):
        """ Reúne a grelha no Rank 0 para desenho """
        # Gather (inverso do Scatter)
        if rank == 0:
            full_grid = np.zeros(self.global_dim, dtype=np.uint8)
        else:
            full_grid = None
            
        # Nota: Gather espera receber em lista de chunks se tamanhos iguais
        # Gatherv é mais seguro, mas para divisão exata Gather funciona com numpy buffers
        # O mpi4py com numpy faz o gather automaticamente concatenando se usarmos a sintaxe correta
        
        # Opção segura: Gather devolve lista de arrays no rank 0
        recv_list = comm.gather(self.cells, root=0)
        
        if rank == 0:
            full_grid = np.vstack(recv_list)
            self.global_cells = full_grid
            
        return self.global_cells

class App:
    """ Mantive sua classe App quase idêntica, mas otimizei o draw """
    def __init__(self, geometry, grid):
        self.grid = grid
        self.size_x = geometry[1]//grid.global_dim[1]
        self.size_y = geometry[0]//grid.global_dim[0]
        self.width = grid.global_dim[1] * self.size_x
        self.height= grid.global_dim[0] * self.size_y
        self.screen = pg.display.set_mode((self.width,self.height))
        self.col_dead = grid.col_dead
        self.col_life = grid.col_life

    def draw(self):
        # OTIMIZAÇÃO CRÍTICA: Se não usar isso, o display será o gargalo, não o cálculo.
        # Convertemos a matriz numpy diretamente para pixels surface
        # Mapeamento simples: 0 -> cor morta, 1 -> cor viva
        
        # Pegar grelha global atualizada
        matrix = self.grid.global_cells
        
        # Criar array de cores (Transposta porque o Pygame usa (x, y) e numpy usa (row, col))
        # Se matrix é (rows, cols), pygame quer (width, height) = (cols, rows)
        matrix_T = matrix.T 
        
        # Construir superfície RGB
        surf_array = np.zeros((self.width, self.height, 3), dtype=np.uint8)
        
        # Preencher (simplificado para blocos sólidos é difícil sem loop, 
        # mas podemos usar escala se 1 pixel = 1 célula)
        
        # Método Híbrido Rápido: Desenhar retângulos ainda é lento, 
        # mas vamos manter seu método original se quiser medir a lentidão, 
        # ou usar este método rápido:
        
        self.screen.fill(self.col_dead)
        # Obter coordenadas das células vivas
        rows, cols = np.where(matrix == 1)
        
        # Desenhar apenas as vivas (muito mais rápido que desenhar todas)
        for r, c in zip(rows, cols):
            rect = (c * self.size_x, r * self.size_y, self.size_x, self.size_y)
            pg.draw.rect(self.screen, self.col_life, rect)

        pg.display.update()

if __name__ == '__main__':
    # Configuração igual ao seu original
    dico_patterns = {
        'blinker' : ((5,5),[(2,1),(2,2),(2,3)]),
        'toad'    : ((6,6),[(2,2),(2,3),(2,4),(3,3),(3,4),(3,5)]),
        "acorn"   : ((100,100), [(51,52),(52,54),(53,51),(53,52),(53,55),(53,56),(53,57)]),
        "beacon"  : ((6,6), [(1,3),(1,4),(2,3),(2,4),(3,1),(3,2),(4,1),(4,2)]),
        "boat" : ((5,5),[(1,1),(1,2),(2,1),(2,3),(3,2)]),
        "glider": ((100,90),[(1,1),(2,2),(2,3),(3,1),(3,2)]),
        "glider_gun": ((200,200),[(51,76),(52,74),(52,76),(53,64),(53,65),(53,72),(53,73),(53,86),(53,87),(54,63),(54,67),(54,72),(54,73),(54,86),(54,87),(55,52),(55,53),(55,62),(55,68),(55,72),(55,73),(56,52),(56,53),(56,62),(56,66),(56,68),(56,69),(56,74),(56,76),(57,62),(57,68),(57,76),(58,63),(58,67),(59,64),(59,65)]),
        "space_ship": ((25,25),[(11,13),(11,14),(12,11),(12,12),(12,14),(12,15),(13,11),(13,12),(13,13),(13,14),(14,12),(14,13)]),
        "die_hard" : ((100,100), [(51,57),(52,51),(52,52),(53,52),(53,56),(53,57),(53,58)]),
        "pulsar": ((17,17),[(2,4),(2,5),(2,6),(7,4),(7,5),(7,6),(9,4),(9,5),(9,6),(14,4),(14,5),(14,6),(2,10),(2,11),(2,12),(7,10),(7,11),(7,12),(9,10),(9,11),(9,12),(14,10),(14,11),(14,12),(4,2),(5,2),(6,2),(4,7),(5,7),(6,7),(4,9),(5,9),(6,9),(4,14),(5,14),(6,14),(10,2),(11,2),(12,2),(10,7),(11,7),(12,7),(10,9),(11,9),(12,9),(10,14),(11,14),(12,14)]),
        "floraison" : ((40,40), [(19,18),(19,19),(19,20),(20,17),(20,19),(20,21),(21,18),(21,19),(21,20)]),
        "block_switch_engine" : ((400,400), [(201,202),(201,203),(202,202),(202,203),(211,203),(212,204),(212,202),(214,204),(214,201),(215,201),(215,202),(216,201)]),
        "u" : ((200,200), [(101,101),(102,102),(103,102),(103,101),(104,103),(105,103),(105,102),(105,101),(105,105),(103,105),(102,105),(101,105),(101,104)]),
        "flat" : ((200,400), [(80,200),(81,200),(82,200),(83,200),(84,200),(85,200),(86,200),(87,200), (89,200),(90,200),(91,200),(92,200),(93,200),(97,200),(98,200),(99,200),(106,200),(107,200),(108,200),(109,200),(110,200),(111,200),(112,200),(114,200),(115,200),(116,200),(117,200),(118,200)])
    }
    
    # Argumentos
    choice = 'glider'
    if len(sys.argv) > 1 : choice = sys.argv[1]
    resx = 800
    resy = 800
    if len(sys.argv) > 3 :
        resx = int(sys.argv[2])
        resy = int(sys.argv[3])

    # Apenas Rank 0 imprime infos
    if rank == 0:
        print(f"Pattern initial choisi : {choice}")
        print(f"resolution ecran : {resx,resy}")
        pg.init() # Init pygame apenas no mestre
    
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        if rank == 0: print("No such pattern. Available ones are:", dico_patterns.keys())
        sys.exit(1)

    # 1. Criar Grid (Todos os processos criam sua parte local)
    grid = Grille(*init_pattern)
    
    # 2. Criar App (Apenas Rank 0)
    appli = None
    if rank == 0:
        appli = App((resx, resy), grid)

    mustContinue = True
    while mustContinue:
        # Sincronização de tempo (opcional, para medir performance correta)
        comm.Barrier()
        t1 = time.time()
        
        # A. CALCULO (Todos trabalham)
        grid.compute_next_iteration()
        t2 = time.time()
        
        # B. VISUALIZAÇÃO (Gather -> Desenho no Rank 0)
        grid.get_global_grid() # Reúne dados no rank 0
        
        if rank == 0:
            appli.draw()
            t3 = time.time()
            
            # Eventos Pygame
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    mustContinue = False
            
            # Print performance
            print(f"Calc: {t2-t1:2.2e}s | Affich: {t3-t2:2.2e}s\r", end='')

        # Sincronizar decisão de sair
        # Se Rank 0 decidiu sair (mustContinue=False), avisa os outros
        mustContinue = comm.bcast(mustContinue, root=0)

    if rank == 0:
        pg.quit()