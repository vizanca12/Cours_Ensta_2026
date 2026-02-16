"""
Jeu de la vie - Version parallèle MPI
Basé sur le code original de l'utilisateur, adapté pour la décomposition du domaine.
"""
from mpi4py import MPI
import pygame as pg
import numpy as np
import sys
import time
from scipy.signal import convolve2d

# --- Configuration MPI ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

class Grille:
    def __init__(self, dim, init_pattern=None, color_life=pg.Color("black"), color_dead=pg.Color("white")):
        self.global_dim = dim
        self.col_life = color_life
        self.col_dead = color_dead
        
        # 1. Décomposition du domaine
        if dim[0] % size != 0:
            if rank == 0: print("Erreur : la hauteur doit être divisible par le nombre de processus.")
            sys.exit(1)
            
        self.local_h = dim[0] // size
        self.local_w = dim[1]
        self.local_dim = (self.local_h, self.local_w)
        
        # 2. Initialisation globale (seulement sur le rang 0)
        self.global_cells = None # Garante que existe em todos os ranks
        if rank == 0:
            if init_pattern is not None:
                self.global_cells = np.zeros(dim, dtype=np.uint8)
                indices_i = [v[0] for v in init_pattern]
                indices_j = [v[1] for v in init_pattern]
                self.global_cells[indices_i, indices_j] = 1
            else:
                self.global_cells = np.random.randint(2, size=dim, dtype=np.uint8)

        # 3. Distribution (Scatter)
        # Prépare le buffer local
        self.cells = np.zeros(self.local_dim, dtype=np.uint8)
        
        # CORRECTION ICI : Nous passons la matrice entière. Le Scatter la divise lui-même.
        # Sendbuf: (buffer, count, type) ou simplement le buffer si la division est égale
        # mpi4py divise automatiquement le premier axe (lignes).
        comm.Scatter(self.global_cells, self.cells, root=0)

    @staticmethod        
    def h(x):
        """
        Applique les règles du Jeu de la vie en utilisant des opérations vectorisées.
        Entrée: x est la matrice contenant le nombre de voisins vivants de chaque cellule.
        Sortie: Matrice des changements à appliquer.
        Règles:
        - Cellules avec <=1 voisin : meurent par sous-population
        - Cellules avec >=4 voisins : meurent par sur-population
        - Cellules avec 2 voisins : conservent leur état
        - Cellules avec 3 voisins : naissent ou restent vivantes
        """
        x[x <= 1] = -1   # Meurt par sous-population
        x[x >= 4] = -1   # Meurt par sur-population
        x[x == 2] = 0    # Conserve l'état
        x[x == 3] = 1    # Naît
        return x

    def compute_next_iteration(self):
        """
        Version MPI avec cellules fantômes (échange halo) et convolution vectorisée.
        Implémente la décomposition du domaine avec échanges asynchrones de bords.
        """
        # --- ÉTAPE 1 : Échange des cellules fantômes (Halo Exchange) ---
        # Voisins dans l'anneau toroïdal (tore vertical)
        up_neighbor = (rank - 1) % size
        down_neighbor = (rank + 1) % size

        # Buffers pour recevoir les lignes fantômes des voisins
        ghost_top = np.empty(self.local_w, dtype=np.uint8)
        ghost_bottom = np.empty(self.local_w, dtype=np.uint8)

        # Échanges non bloquants (Isend/Irecv) pour de meilleures performances
        # Chaque processus envoie sa bordure supérieure au voisin supérieur et reçoit la bordure inférieure
        # Simultanément, envoie la bordure inférieure au voisin inférieur et reçoit la bordure supérieure
        req1 = comm.Isend(self.cells[0, :], dest=up_neighbor, tag=11)
        req2 = comm.Irecv(ghost_bottom, source=down_neighbor, tag=11)
        req3 = comm.Isend(self.cells[-1, :], dest=down_neighbor, tag=22)
        req4 = comm.Irecv(ghost_top, source=up_neighbor, tag=22)

        MPI.Request.Waitall([req1, req2, req3, req4])
        
        # --- ÉTAPE 2 : Construire la matrice étendue (avec cellules fantômes) ---
        # On combine : ligne fantôme supérieure + données locales + ligne fantôme inférieure
        expanded_cells = np.vstack([ghost_top, self.cells, ghost_bottom])
        
        # --- ÉTAPE 3 : Calcul vectorisé (convolution 2D) ---
        # Noyau 3x3 de uns (convolution pour compter les voisins)
        C = np.ones((3, 3))
        C[1, 1] = 0  # On ne compte pas la cellule centrale

        # La convolution avec 'boundary=wrap' crée un tore sur les côtés (droite-gauche)
        # La dimension verticale est gérée par les cellules fantômes
        voisins = convolve2d(expanded_cells, C, mode='same', boundary='wrap')
        
        # Retirer les lignes de cellules fantômes du résultat pour revenir à la taille locale
        voisins = voisins[1:-1, :]
        
        # --- ÉTAPE 4 : Appliquer les règles du Jeu de la vie (vectorisé) ---
        # Une cellule vivante (1) survit si elle a 2 ou 3 voisins
        # Une cellule morte (0) naît si elle a exactement 3 voisins
        next_cells = np.zeros(self.cells.shape, dtype=np.uint8)
        next_cells[(self.cells == 1) & ((voisins == 2) | (voisins == 3))] = 1
        next_cells[(self.cells == 0) & (voisins == 3)] = 1
        
        self.cells = next_cells
        return []

    def get_global_grid(self):
        """
        Rassemble (Gather) la grille distribuée sur le rang 0 pour la visualisation.
        Utilise la méthode gather du MPI qui concatène automatiquement les données de chaque processus.
        Retourne la grille globale complète sur le rang 0, None sur les autres processus.
        """
        # Utiliser gather pour rassembler les données de tous les processus sur le rang 0
        # mpi4py avec numpy renvoie une liste de tableaux sur le rang 0
        recv_list = comm.gather(self.cells, root=0)
        
        if rank == 0:
            # Concaténer verticalement les parties de chaque processus
            full_grid = np.vstack(recv_list)
            self.global_cells = full_grid
            return full_grid
        else:
            return None

class App:
    """J'ai gardé la classe App presque identique, mais j'ai optimisé le dessin."""
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
        # OPTIMISATION CRITIQUE : Si on n'utilise pas cela, l'affichage sera le goulot d'étranglement, pas le calcul.
        # Nous convertissons la matrice numpy directement en surface de pixels
        # Mappage simple : 0 -> couleur morte, 1 -> couleur vivante

        # Récupérer la grille globale mise à jour
        matrix = self.grid.global_cells

        # Créer un tableau de couleurs (transposée car Pygame utilise (x, y) et numpy utilise (ligne, colonne))
        # Si matrix est (lignes, colonnes), pygame veut (largeur, hauteur) = (colonnes, lignes)
        matrix_T = matrix.T

        # Construire la surface RGB (optionnel si on dessine par blocs)
        surf_array = np.zeros((self.width, self.height, 3), dtype=np.uint8)

        # Méthode hybride rapide : dessiner uniquement les cellules vivantes
        self.screen.fill(self.col_dead)
        # Obtenir les coordonnées des cellules vivantes
        rows, cols = np.where(matrix == 1)

        # Dessiner uniquement les vivantes (beaucoup plus rapide que dessiner toutes)
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
        print(f"Motif initial choisi : {choice}")
        print(f"résolution écran : {resx,resy}")
        pg.init() # Initialiser pygame seulement sur le maître
    
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        if rank == 0: print("Motif inconnu. Les motifs disponibles sont :", dico_patterns.keys())
        sys.exit(1)

    # 1. Créer la grille (tous les processus créent leur partie locale)
    grid = Grille(*init_pattern)

    # 2. Créer l'application (seulement sur le rang 0)
    appli = None
    if rank == 0:
        appli = App((resx, resy), grid)

    mustContinue = True
    while mustContinue:
        # Synchronisation temporelle (optionnelle, pour mesurer correctement la performance)
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

            # Événements Pygame
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    mustContinue = False

            # Afficher les performances
            print(f"Calc: {t2-t1:2.2e}s | Affichage: {t3-t2:2.2e}s\r", end='')

        # Sincronizar decisão de sair
        # Se Rank 0 decidiu sair (mustContinue=False), avisa os outros
        mustContinue = comm.bcast(mustContinue, root=0)

    if rank == 0:
        pg.quit()
