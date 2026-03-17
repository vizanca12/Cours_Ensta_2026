/*
 * ant.hpp
 *
 * Este arquivo define a classe ant, que representa uma formiga individual
 * dentro da simulacao ACO.
 *
 * Responsabilidades principais:
 * 1) Guardar estado local da formiga (posicao, se esta carregada, semente RNG).
 * 2) Expor operacoes de transicao de estado (carregada/nao carregada).
 * 3) Executar um passo de movimento com base no terreno e nos feromonios.
 *
 * Observacao: o coeficiente de exploracao (m_eps) e estatico, ou seja,
 * compartilhado por todas as formigas.
 */
#ifndef _ANT_HPP_
# define _ANT_HPP_
# include <vector>
# include <utility>
# include "pheronome.hpp"
# include "fractal_land.hpp"
# include "basic_types.hpp"

class ant
{
public:
    /*
     * Estado comportamental da formiga:
     * - unloaded: procurando comida.
     * - loaded: carregando comida de volta ao ninho.
     */
    /**
     * Une fourmi peut être dans deux états possibles : chargée ( elle porte de la nourriture ) ou non chargée
     */
    enum state { unloaded = 0, loaded = 1 };
    ant(const position_t& pos, std::size_t seed ) : m_seed(seed), m_state(unloaded), m_position(pos)
    {}
    ant(const ant& a) = default;
    ant( ant&& a ) = default;
    ~ant() = default;

    void set_loaded() { m_state = loaded; }
    void unset_loaded() { m_state = unloaded; }

    bool is_loaded() const { return m_state == loaded; }
    const position_t& get_position() const { return m_position; }

    /*
     * Configuracao global de exploracao:
     * valores maiores aumentam movimento aleatorio,
     * valores menores favorecem seguir feromonio.
     */
    static void set_exploration_coef(double eps) { m_eps = eps; }

    /*
     * Rotina principal de dinamica da formiga em um passo de tempo:
     * - escolhe movimento (exploracao ou guiado por feromonio),
     * - atualiza posicao,
     * - marca feromonio,
     * - atualiza contador de comida quando retorna ao ninho.
     */
    void advance( pheronome& phen, const fractal_land& land,
                  const position_t& pos_food, const position_t& pos_nest,
                  std::size_t& cpteur_food, std::vector<position_t>* pheromone_marks = nullptr );

private:
    static double m_eps; // Coefficient d'exploration commun à toutes les fourmis.
    std::size_t m_seed;
    state m_state;
    position_t m_position;
};

#endif