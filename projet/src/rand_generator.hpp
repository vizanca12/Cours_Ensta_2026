/*
 * rand_generator.hpp
 *
 * Geracao pseudo-aleatoria leve para simulacao numerica.
 *
 * Prioridades deste modulo:
 * - reproducibilidade (mesma seed -> mesmo resultado),
 * - custo baixo por chamada,
 * - simplicidade de integracao no codigo.
 *
 * Nao e um gerador para seguranca/criptografia.
 */
#pragma once
#include <cstdint>
#include <cmath> 

struct RandomGenerator
{
    /*
     * Gerador parametrizado por faixa [min,max] para ruido do terreno.
     */
    std::uint32_t m_seed;
    double m_min_val;
    double m_max_val;
    RandomGenerator(std::size_t seed, double min_val, double max_val)
        : m_seed(static_cast<std::uint32_t>(seed)),
          m_min_val(min_val),
          m_max_val(max_val) {}

    double operator() (int i, int j) const
    {
        std::size_t local_seed = m_seed + i * 73856093 + j * 19349663;
        local_seed = (1664525 * local_seed + 1013904223) % 0xFFFFFFFF;
        return m_min_val + std::fmod(local_seed, (m_max_val - m_min_val + 1));
    }

};

inline
std::int32_t rand_int32 ( std::int32_t min_val, std::int32_t max_val, std::size_t& seed )
{
    // Inteiro uniforme aproximado usando LCG com estado mutavel por referencia.
    seed = (1664525 * seed + 1013904223) % 0xFFFFFFFF;
    return min_val + seed % ( max_val - min_val + 1 );
}

inline double rand_double ( double min_val, double max_val, std::size_t& seed )
{
    // Versao em ponto flutuante, reutilizando a mesma evolucao de estado.
    seed = (1664525 * seed + 1013904223) % 0xFFFFFFFF;
    return min_val + std::fmod( seed, ( max_val - min_val + 1 ) );
}
