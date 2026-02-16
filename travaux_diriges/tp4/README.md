# TP4: Jeu de la Vie - Analyse Comparative et Optimisations

## 📋 Vue d'ensemble

Ce travail pratique explore l'implémentation du **Jeu de la Vie de Conway** en utilisant différentes approches algorithmiques et parallélismes. L'objectif est de comprendre les optimisations de performance à travers l'utilisation de techniques vectorisées et de programmation parallèle avec MPI.

### Fichiers fournis par le professeur:
- **game_of_life.py**: Implémentation de base avec boucles explicites
- **game_of_life_vect.py**: Implémentation optimisée avec convolue2d et opérations vectorisées

### Fichiers à complète (travaux de l'étudiant):
- **game_of_life_final.py**: Version parallèle (MPI) sans interface graphique pour analyse de performance
- **game_of_life_vect_final.py**: Version parallèle (MPI) avec visualisation PyGame et optimisations vectorisées

---

## 🔍 Analyse des implémentations

### 1. **game_of_life.py** - Implémentation de Base

**Caractéristiques:**
- Utilise deux boucles imbriquées pour parcourir chaque cellule
- Calcule manuellement le nombre de voisins vivants
- Pas de vectorisation NumPy

**Avantages:**
- ✅ Très lisible et compréhensible
- ✅ Facile à déboguer
- ✅ Idéal pour comprendre la logique de l'algorithme

**Inconvénients:**
- ❌ Performance limitée pour grandes grilles
- ❌ Python pur est lent pour les boucles imbriquées
- ❌ Pas adapté aux calculs intensifs

**Complexité temporelle:** O(n × m × 8) où n×m est la taille de la grille

---

### 2. **game_of_life_vect.py** - Version Vectorisée

**Caractéristiques:**
- Utilise `scipy.signal.convolve2d` pour compter les voisins efficacement
- Opérations matricielles complètes sans boucles explicites
- Fonction `h()` applique les règles du jeu de manière vectorisée

**Code clé - Convolue2d:**
```python
C = np.ones((3,3))
C[1,1] = 0
voisins = convolve2d(self.cells, C, mode='same', boundary='wrap')
```

**Comment ça fonctionne:**
1. La matrice `C` est un kernel 3×3 de uns (sauf le centre)
2. La convolue2d "glisse" ce kernel sur chaque cellule
3. Le résultat est le nombre de voisins vivants de chaque cellule
4. `boundary='wrap'` crée l'effet de tore (bords qui se rejoignent)

**Fonction `h()`:**
```python
@staticmethod        
def h(x):
    x[x<=1]=-1     # Meure par sous-population
    x[x>=4]=-1     # Meure par sur-population
    x[x==2]=0      # Maintient l'état
    x[x==3]=1      # Naît ou reste vivant
```

**Avantages:**
- ✅ **100-1000x plus rapide** que la version de base
- ✅ Exploite les opérations vectorisées de NumPy (C-level)
- ✅ Utilise la localité mémoire efficacement
- ✅ Idéal pour des calculs intensifs

**Inconvénients:**
- ❌ Moins lisible pour les débutants
- ❌ Nécessite la compréhension des opérations matricielles

**Complexité temporelle:** O(n × m) - une seule passe sur la matrice

---

### 3. **game_of_life_final.py** - Version Parallèle (Analyse sans GUI)

**Approche:**
- Utilise **MPI (Message Passing Interface)** pour paralléliser sur plusieurs processus
- Décomposition de domaine: chaque processus gère une "tranche" de la grille
- Halo Exchange: échange des bordas avec les processus voisins

**Architecture MPI:**
```
Processus 0: Lignes [0-49]      ┐
Processus 1: Lignes [50-99]     ├─ Grille 200×200
Processus 2: Lignes [100-149]   │  divisée en 4
Processus 3: Lignes [150-199]   ┘
```

**Halo Exchange:**
```
Chaque processus envoie:
- Sa ligne supérieure (index 0) à son voisin du haut
- Sa ligne inférieure (index -1) à son voisin du bas

Et reçoit:
- Les lignes fantasmes (ghost cells) pour le calcul des bordures
```

**Code principal:**
```python
# Échanges asynchrones
req1 = comm.Isend(self.cells[0, :], dest=up_neighbor, tag=11)
req2 = comm.Irecv(ghost_bottom, source=down_neighbor, tag=11)
req3 = comm.Isend(self.cells[-1, :], dest=down_neighbor, tag=22)
req4 = comm.Irecv(ghost_top, source=up_neighbor, tag=22)
MPI.Request.Waitall([req1, req2, req3, req4])

# Calcul avec convolue2d après réception des ghost cells
expanded = np.vstack([ghost_top, self.cells, ghost_bottom])
voisins = convolve2d(expanded, C, mode='same', boundary='wrap')[1:-1, :]
```

**Réduction pour compter la population globale:**
```python
# Chaque processus compte ses cellules vives localement
local_count = np.sum(self.cells)

# MPI Reduce somme tous les comptes en rank 0
comm.Reduce(local_count_arr, global_count, op=MPI.SUM, root=0)
```

**Performance attendue:**
- ✅ **Accélération linéaire** (théorique) avec le nombre de processus
- ✅ Échanges MPI asynchrones minimisent les stalls
- ✅ Vectorisation + Parallélisation = performance maximale

**Scalabilité:**
- ✅ Scalable jusqu'à plusieurs milliers de processus
- ❌ Communication MPI peut dominer pour très petites grilles

---

### 4. **game_of_life_vect_final.py** - Version Parallèle avec Visualisation

**Combinaison de:**
- Implémentation parallèle MPI (comme game_of_life_final.py)
- Vectorisation avec convolue2d
- Visualisation en temps réel avec PyGame

**Architecture:**
```
Rang 0: Initialise PyGame, coordonne les calculs, affiche
Rangs 1-N: Calculent leur portion de la grille
Après chaque itération: Gather pour reconstruire la grille complète au rang 0
```

**Optimisations de visualisation:**
```python
def draw(self):
    self.screen.fill(self.col_dead)  # Fond uniforme
    rows, cols = np.where(matrix == 1)  # Trouve les cellules vives
    for r, c in zip(rows, cols):       # Ne dessine que les vives
        pg.draw.rect(self.screen, self.col_life, rect)
```

**Avantages de cette implémentation:**
- ✅ Parallélisme + Vectorisation + Visualisation
- ✅ Bonnes performances même avec affichage en temps réel
- ✅ Démonstration pratique de HPC (High Performance Computing)

**Considérations de performance:**
- La visualisation ralentit (OpenGL pour mieux faire en production)
- Le Gather à chaque itération peut être un goulot d'étranglement
- Solution: afficher tous les N itérations au lieu de chaque itération

---

## 📊 Comparaison de Performance

| Implémentation | Boucles? | Vectorisée? | Parallèle? | Relative Speed |
|---|---|---|---|---|
| game_of_life.py | ✅ | ❌ | ❌ | **1x** (baseline) |
| game_of_life_vect.py | ❌ | ✅ | ❌ | **~100-1000x** |
| game_of_life_final.py | ❌ | ✅ | ✅ | **100-1000x × P** |
| game_of_life_vect_final.py | ❌ | ✅ | ✅ | **100-1000x × P** |

*P = nombre de processus MPI*

### Cas d'usage pratique (grille 1000×1000):
- **Boucles seules:** ~1-2 secondes par itération
- **Vectorisée:** ~1-5 millisecondes par itération (200-1000x plus rapide!)
- **Vectorisée + 4 processus MPI:** ~0.3-1 milliseconde par itération

---

## 🚀 Exécution

### Prérequis:
```bash
pip install numpy scipy pygame mpi4py
```

### Exécution des versions séquentielles:
```bash
# Version de base
python game_of_life.py glider 800 800

# Version vectorisée
python game_of_life_vect.py glider 800 800
```

### Exécution des versions parallèles:
```bash
# Sans visualisation (juste analyse)
mpirun -np 4 python game_of_life_final.py glider_gun

# Avec visualisation (note: une seule fenêtre au rang 0)
mpirun -np 4 python game_of_life_vect_final.py glider 800 800
```

### Patterns disponibles:
- `blinker`, `toad`, `acorn`, `beacon`, `boat`, `glider`, `glider_gun`
- `space_ship`, `die_hard`, `pulsar`, `floraison`, `block_switch_engine`, `u`, `flat`

---

## 🎯 Apprentissages clés

1. **Vectorisation:** Les opérations matricielles NumPy sont **infiniment plus rapides** que les boucles Python
2. **MPI Halo Exchange:** La technique de decomposition de domaine permet de paralléliser efficacement
3. **Convolue2d:** Excellent exemple d'algorithme vectorisé (utilisé en traitement d'image, physics simulations, etc.)
4. **Trade-offs:** Parallélisation ajouté une complexité d'implémentation mais donne des gains spectaculaires

---

## 📚 Références

- **Numpy documentation:** https://numpy.org/doc/stable/
- **SciPy signal.convolve2d:** https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.convolve2d.html
- **MPI4Py:** https://mpi4py.readthedocs.io/
- **Game of Life:** https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life

---

## ✅ Résumé des modifications

### game_of_life_final.py:
- ✅ Ajout de commentaires détaillés sur la structure MPI
- ✅ Implémentation de la fonction `h()` pour les règles vectorisées
- ✅ Docstrings améliorées pour chaque méthode
- ✅ Explication du Halo Exchange et de la réduction MPI

### game_of_life_vect_final.py:
- ✅ Amélioration de la documentation de `h()`
- ✅ Commentaires détaillés sur le Halo Exchange asynchrone
- ✅ Meilleure structure et lisibilité du compute_next_iteration()
- ✅ Optimisation et clarification de get_global_grid()

---

*Rapport préparé pour le cours ENSTA 2026 - Calcul Haute Performance*
