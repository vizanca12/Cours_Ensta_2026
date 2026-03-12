#include "ant.hpp"
#include <iostream>
#include "rand_generator.hpp"

double ant::m_eps = 0.;

void ant::advance( pheronome& phen, const fractal_land& land, const position_t& pos_food, const position_t& pos_nest,
                   std::size_t& cpteur_food ) 
{
    constexpr double k_min_step_cost = 1e-3;
    constexpr int k_max_substeps = 4096;
    constexpr int k_max_random_tries = 64;
    auto ant_choice = [this]() mutable { return rand_double( 0., 1., this->m_seed ); };
    auto dir_choice = [this]() mutable { return rand_int32( 1, 4, this->m_seed ); };
    double                                   consumed_time = 0.;
    int substeps = 0;
    // Tant que la fourmi peut encore bouger dans le pas de temps imparti
    while ( ( consumed_time < 1. ) && ( substeps < k_max_substeps ) ) {
        // Si la fourmi est chargée, elle suit les phéromones de deuxième type, sinon ceux du premier.
        int        ind_pher    = ( is_loaded( ) ? 1 : 0 );
        double     choix       = ant_choice( );
        position_t old_pos_ant = get_position( );
        position_t new_pos_ant = old_pos_ant;
        double max_phen    = std::max( {phen( new_pos_ant.x - 1, new_pos_ant.y )[ind_pher],
                                     phen( new_pos_ant.x + 1, new_pos_ant.y )[ind_pher],
                                     phen( new_pos_ant.x, new_pos_ant.y - 1 )[ind_pher],
                                     phen( new_pos_ant.x, new_pos_ant.y + 1 )[ind_pher]} );
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
        phen.mark_pheronome( new_pos_ant );
        m_position = new_pos_ant;
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