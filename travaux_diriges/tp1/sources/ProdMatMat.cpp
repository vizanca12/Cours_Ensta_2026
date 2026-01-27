#include <algorithm>
#include <cassert>
#include <iostream>
#include "ProdMatMat.hpp"

namespace {
// Esta função processa apenas um pequeno "tijolo" (bloco) da matriz por vez
void prodSubBlocks(int iRow, int jCol, int kDim, int szBlock,
                   const Matrix& A, const Matrix& B, Matrix& C) {
    // Definimos os limites para não ultrapassar o tamanho da matriz
    int limitI = std::min(A.nbRows, iRow + szBlock);
    int limitJ = std::min(B.nbCols, jCol + szBlock);
    int limitK = std::min(A.nbCols, kDim + szBlock);

    // Seguindo a sua sequência j, k, i (mas verifique se i, k, j não é mais rápida no seu PC)
    for (int j = jCol; j < limitJ; ++j) {
        for (int k = kDim; k < limitK; ++k) {
            for (int i = iRow; i < limitI; ++i) {
                C(i, j) += A(i, k) * B(k, j);
            }
        }
    }
}
const int szBlock = 32; // Tamanho que você identificou como ótimo [cite: 46]
}  // namespace

Matrix operator*(const Matrix& A, const Matrix& B) {
    Matrix C(A.nbRows, B.nbCols, 0.0);
    
    // TRÊS LOOPS EXTERNOS: Eles dividem a matriz em blocos de tamanho szBlock [cite: 41, 45]
    for (int i = 0; i < A.nbRows; i += szBlock) {
        for (int k = 0; k < A.nbCols; k += szBlock) {
            for (int j = 0; j < B.nbCols; j += szBlock) {
                // Aqui processamos o bloco C(i,j) usando pedaços de A e B
                prodSubBlocks(i, j, k, szBlock, A, B, C);
            }
        }
    }
    return C;
}