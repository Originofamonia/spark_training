# http://ampcamp.berkeley.edu/5/exercises/movie-recommendation-with-mllib.html
# https://weiminwang.blog/2016/06/09/pyspark-tutorial-building-a-random-forest-binary-classifier-on-unbalanced-dataset/
"""
    1. use sklearn's MF (done)
    2. this baseline is MF(x_train)
"""
import sys
import itertools
import os
import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from sklearn.decomposition import NMF
from sklearn.metrics import roc_auc_score
# from operator import add
# from os.path import join, isfile, dirname


def add_path(path):
    if path not in sys.path:
        print('Adding {}'.format(path))
        sys.path.append(path)


abs_current_path = os.path.realpath('./')
root_path = os.path.join('/', *abs_current_path.split(os.path.sep)[:-2])
lib_dir = os.path.join(root_path, 'lib')
add_path(root_path)


from machine_learning.movieLens.MovieLens_spark_hcf import generate_xoy, generate_xoy_binary, split_ratings,\
    compute_t, sigmoid, load_ratings
from machine_learning.movieLens.MovieLens_sklearn_hcf import mf_sklearn


def normalize_s(x_train):

    s_norm = (x_train - np.mean(x_train)) / np.std(x_train)
    s = sigmoid(s_norm)
    return s


def baseline2_inference(s_hat, test, rating_sahpe):
    """
    sklearn version AUROC
    """
    # x_train, o_train, y_train = generate_xoy_binary(training, rating_sahpe)
    x_test, o_test, y_test = generate_xoy_binary(test, rating_sahpe)

    y_scores = s_hat[o_test > 0]  # exclude unobserved
    y_true = x_test[o_test > 0] 
    auc = roc_auc_score(y_true, y_scores)
    return auc


def main():
    # load personal ratings
    movie_lens_home_dir = '../../data/movielens/medium/'
    path = '../../data/movielens/medium/ratings.dat'
    ratings = load_ratings(path)
    training, validation, test = split_ratings(ratings, 6, 8)

    x_train, o_train, y_train = generate_xoy(training, (6041, 3953))

    s = normalize_s(x_train)

    ranks = [30, 40]
    num_iters = [50, 80]
    best_t = None
    best_validation_auc = float("-inf")
    best_rank = 0

    best_num_iter = -1

    for rank, num_iter in itertools.product(ranks, num_iters):
        s_hat = mf_sklearn(s, n_components=rank, n_iter=num_iter)  # [0, 23447]
        valid_auc = baseline2_inference(s_hat, validation, (6041, 3953))
        print("The current model was trained with rank = {}, and num_iter = {}, and its AUC on the "
              "validation set is {}.".format(rank, num_iter, valid_auc))
        if valid_auc > best_validation_auc:
            best_t = s_hat
            best_validation_auc = valid_auc
            best_rank = rank
            best_num_iter = num_iter

    test_auc = baseline2_inference(best_t, test, (6041, 3953))
    print("The best model was trained with rank = {}, and num_iter = {}, and its AUC on the "
          "test set is {}.".format(best_rank, best_num_iter, test_auc))


if __name__ == "__main__":
    main()
