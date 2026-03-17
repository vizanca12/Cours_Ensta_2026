/*
 * ant.cpp
 *
 * Este arquivo implementa o "comportamento local" da formiga.
 *
 * O metodo advance() e o nucleo da simulacao de agentes:
 * - recebe o estado global (terreno + feromonio),
 * - aplica regras estocasticas de movimento,
 * - atualiza estado interno da formiga,
 * - contribui para o campo de feromonio.
 *
 * Resultado pratico:
 * muitas chamadas de advance() em paralelo formam a dinamica coletiva.
 */
#include "ant.hpp"
#include <iostream>
#include "rand_generator.hpp"

double ant::m_eps = 0.;

void ant::advance( pheronome& phen, const fractal_land& land, const position_t& pos_food, const position_t& pos_nest,
                   std::size_t& cpteur_food, std::vector<position_t>* pheromone_marks ) 
{
    /*
     * Guardas numericas de seguranca:
     * - k_min_step_cost: evita incremento quase zero de tempo consumido.
     * - k_max_substeps: limita o numero de submovimentos no mesmo passo.
     * - k_max_random_tries: limita tentativas de escolha aleatoria valida.
     */
    constexpr double k_min_step_cost = 1e-3;
    constexpr int k_max_substeps = 4096;
    constexpr int k_max_random_tries = 64;
    auto ant_choice = [this]() mutable { return rand_double( 0., 1., this->m_seed ); };
    auto dir_choice = [this]() mutable { return rand_int32( 1, 4, this->m_seed ); };
    double                                   consumed_time = 0.;
    int substeps = 0;
    /*
     * Cada iteracao do while representa um submovimento da formiga.
     * O loop termina quando a formiga "gasta" 1 unidade de tempo de movimento.
     */
    while ( ( consumed_time < 1. ) && ( substeps < k_max_substeps ) ) {
        // Escolhe canal de feromonio conforme estado da formiga.
        int        ind_pher    = ( is_loaded( ) ? 1 : 0 );
        double     choix       = ant_choice( );
        position_t old_pos_ant = get_position( );
        position_t new_pos_ant = old_pos_ant;
        double max_phen    = std::max( {phen( new_pos_ant.x - 1, new_pos_ant.y )[ind_pher],
                                     phen( new_pos_ant.x + 1, new_pos_ant.y )[ind_pher],
                                     phen( new_pos_ant.x, new_pos_ant.y - 1 )[ind_pher],
                                     phen( new_pos_ant.x, new_pos_ant.y + 1 )[ind_pher]} );
        /*
         * Politica de acao (exploracao vs exploracao guiada):
         * - componente aleatoria ajuda a descobrir novos caminhos,
         * - componente gulosa (max feromonio) explora trilhas ja aprendidas.
         */
        if ( ( choix > m_eps ) || ( max_phen <= 0. ) ) {
            bool found = false;
            for ( int tries = 0; tries < k_max_random_tries; ++tries ) {
                new_pos_ant = old_pos_ant;
                int d = dir_choice();
                if ( d==1 ) new_pos_ant.x  -= 1;
                if ( d==2 ) new_pos_ant.y -= 1;
                if ( d==3 ) new_pos_ant.x  += 1;
                if ( d==4 ) new_pos_ant.y += 1;
                if ( phen[new_pos_ant][ind_pher] != -1 ) {
                    found = true;
                    break;
                }
            }
            if ( !found ) {
                new_pos_ant = old_pos_ant;
            }
        } else {
            // On choisit la case où le phéromone est le plus fort.
            if ( phen( new_pos_ant.x - 1, new_pos_ant.y )[ind_pher] == max_phen )
                new_pos_ant.x -= 1;
            else if ( phen( new_pos_ant.x + 1, new_pos_ant.y )[ind_pher] == max_phen )
                new_pos_ant.x += 1;
            else if ( phen( new_pos_ant.x, new_pos_ant.y - 1 )[ind_pher] == max_phen )
                new_pos_ant.y -= 1;
            else  // if (phen(new_pos_ant.first,new_pos_ant.second+1)[ind_pher] == max_phen)
                new_pos_ant.y += 1;
        }
        consumed_time += std::max( land( new_pos_ant.x, new_pos_ant.y), k_min_step_cost );
        ++substeps;
        if ( pheromone_marks != nullptr ) {
            pheromone_marks->push_back( new_pos_ant );
        } else {
            phen.mark_pheronome( new_pos_ant );
        }
        m_position = new_pos_ant;
        /*
         * Maquina de estados da formiga:
         * - ao atingir ninho: descarrega comida (se houver) e volta a buscar.
         * - ao atingir comida: muda para estado carregada e passa a retornar.
         */
        if ( get_position( ) == pos_nest ) {
            if ( is_loaded( ) ) {
                cpteur_food += 1;
            }
            unset_loaded( );
        }
        if ( get_position( ) == pos_food ) {
            set_loaded( );
        }
    }
}