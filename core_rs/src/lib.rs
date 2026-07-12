use pyo3::prelude::*;
use pyo3::types::PyList;
use ndarray::{Array1, Array2, Axis};
use std::cmp::Ordering;

/// Calcula la similitud de coseno entre un vector de consulta y una matriz de documentos.
/// Retorna los \u00edndices y scores ordenados de mayor a menor relevancia.
#[pyfunction]
fn cosine_similarity_search(
    py: Python,
    query_vector: Vec<f32>,
    document_vectors: Vec<Vec<f32>>,
    top_k: usize,
) -> PyResult<PyObject> {
    if document_vectors.is_empty() {
        return Ok(PyList::empty(py).to_object(py));
    }

    let q = Array1::from(query_vector);
    
    // Convertimos document_vectors a Array2
    let rows = document_vectors.len();
    let cols = document_vectors[0].len();
    let mut docs = Array2::zeros((rows, cols));
    
    for (i, row) in document_vectors.iter().enumerate() {
        for (j, &val) in row.iter().enumerate() {
            docs[[i, j]] = val;
        }
    }

    // Normalizar query
    let q_norm = q.dot(&q).sqrt();
    let q_normalized = if q_norm > 0.0 { &q / q_norm } else { q };

    // Calcular similitud (Matrix-Vector dot product)
    let similarities = docs.dot(&q_normalized);
    
    // Normalizar resultados por la norma de cada fila (documento)
    let mut scores: Vec<(usize, f32)> = similarities
        .iter()
        .enumerate()
        .map(|(i, &s)| {
            let row = docs.index_axis(Axis(0), i);
            let row_norm = row.dot(&row).sqrt();
            let score = if row_norm > 0.0 { s / row_norm } else { 0.0 };
            (i, score)
        })
        .collect();

    // Ordenar por score descendente
    scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));

    let result = if scores.len() > top_k {
        scores[..top_k].to_vec()
    } else {
        scores
    };

    Ok(result.to_object(py))
}

#[pyfunction]
fn batch_cosine_search(
    py: Python,
    queries: Vec<Vec<f32>>,
    documents: Vec<Vec<f32>>,
    top_k: usize,
) -> PyResult<PyObject> {
    let mut batch_results = Vec::new();
    for q in queries {
        let res = cosine_similarity_search(py, q, documents.clone(), top_k)?;
        batch_results.push(res);
    }
    Ok(batch_results.to_object(py))
}

#[pyfunction]
fn cosine_similarity_search_with_threshold(
    py: Python,
    query_vector: Vec<f32>,
    document_vectors: Vec<Vec<f32>>,
    top_k: usize,
    threshold: f32,
) -> PyResult<PyObject> {
    let q = Array1::from(query_vector);
    let rows = document_vectors.len();
    let cols = document_vectors[0].len();
    let mut docs = Array2::zeros((rows, cols));
    
    for (i, row) in document_vectors.iter().enumerate() {
        for (j, &val) in row.iter().enumerate() {
            docs[[i, j]] = val;
        }
    }

    let q_norm = q.dot(&q).sqrt();
    let q_normalized = if q_norm > 0.0 { &q / q_norm } else { q };

    let similarities = docs.dot(&q_normalized);
    
    let mut scores: Vec<(usize, f32)> = similarities
        .iter()
        .enumerate()
        .map(|(i, &s)| {
            let row = docs.index_axis(Axis(0), i);
            let row_norm = row.dot(&row).sqrt();
            let score = if row_norm > 0.0 { s / row_norm } else { 0.0 };
            (i, score)
        })
        .filter(|&(_, s)| s >= threshold)
        .collect();

    scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));

    let result = if scores.len() > top_k {
        scores[..top_k].to_vec()
    } else {
        scores
    };

    Ok(result.to_object(py))
}

/// M\u00f3dulo Python expuesto
#[pymodule]
fn jas_vector_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(cosine_similarity_search, m)?)?;
    m.add_function(wrap_pyfunction!(batch_cosine_search, m)?)?;
    m.add_function(wrap_pyfunction!(cosine_similarity_search_with_threshold, m)?)?;
    Ok(())
}
