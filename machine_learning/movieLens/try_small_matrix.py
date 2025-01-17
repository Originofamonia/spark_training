import os
import sys

import numpy as np
from pyspark import SparkConf, SparkContext
from pyspark.mllib.recommendation import ALS
from pyspark.sql import SparkSession
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 23})
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Tahoma']


def add_path(path):
    if path not in sys.path:
        print('Adding {}'.format(path))
        sys.path.append(path)


abs_current_path = os.path.realpath('./')
root_path = os.path.join('/', *abs_current_path.split(os.path.sep)[:-1])
lib_dir = os.path.join(root_path, 'lib')
add_path(root_path)
add_path(abs_current_path)

from machine_learning.movieLens.MovieLens_spark_base1 import spark_matrix_completion


def small_matrix_sklearn():
    mat = np.array([(1, 0, 0, 0),
                    (0, 0, 1, 0),
                    (0, 1, 0, 1),
                    (0, 0, 0, 0)])


def try_small_matrix_spark():
    rank = 1
    num_iter = 20
    lmbda = 0.01
    # ratings = [(0, 0, 1),
    #            (1, 2, 1),
    #            (2, 3, 1),
    #            (3, 1, 1)]
    training = [(0, 0, 1.0),
                (1, 1, 1.0)]

    validation = [(0, 0, 1),
                  (0, 1, 1),
                  (1, 0, 1),
                  (1, 1, 1)]
    num_validation = 2

    conf = SparkConf().setAppName("MovieLensALS") \
        .set("spark.executor.memory", "1g")
    sc = SparkContext(conf=conf)
    # spark = SparkSession(sc)  # solve the ParallelRDD issue
    ratings_rdd = sc.parallelize(training)
    validation_rdd = sc.parallelize(validation)
    model = ALS.train(ratings_rdd, rank, num_iter, lmbda, nonnegative=True, seed=44444)
    predictions = model.predictAll(validation_rdd.map(lambda x: (x[0], x[1])))
    pred = predictions.collect()
    print(pred)


def try_spark_symetric_matrix():
    spark = SparkSession.builder \
        .master('local[*]') \
        .config("spark.driver.memory", "7g") \
        .getOrCreate()
    sc = spark.sparkContext
    rank = 2

    list_tuple = [
        (0, 2, 5),

        (1, 1, 1),

        (2, 0, 5),
    ]

    a_rdd = sc.parallelize(list_tuple).repartition(2)
    model = ALS.train(a_rdd, rank, 20, nonnegative=True)
    a_hat = spark_matrix_completion(model, (3, 3), rank)
    print(a_hat)
    print(np.linalg.matrix_rank(a_hat))


def draw_histo():
    # plt.style.use('seaborn-deep')

    base1_div_data = 'base1_div.npy'
    base1_rerank_data = 'base1_rerank.npy'
    hcf1_div_data = 'hcf1_div.npy'
    base1_div = np.load(base1_div_data)
    base1_rerank = np.load(base1_rerank_data)
    hcf1_div = np.load(hcf1_div_data)
    bins = np.linspace(0.2, 1, 30)

    plt.hist([base1_div, base1_rerank, hcf1_div], bins=bins, label=['CF-RT', 'CF-DM', 'HI-RT'])
    plt.legend(loc='upper right', fancybox=True, framealpha=0.1)
    plt.xlabel('Diversity')
    plt.ylabel('#User')
    plt.show()


if __name__ == '__main__':
    draw_histo()
