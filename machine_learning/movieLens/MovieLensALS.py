# http://ampcamp.berkeley.edu/5/exercises/movie-recommendation-with-mllib.html
# https://weiminwang.blog/2016/06/09/pyspark-tutorial-building-a-random-forest-binary-classifier-on-unbalanced-dataset/

import sys
import itertools
from math import sqrt
from operator import add
from os.path import join, isfile, dirname

from pyspark import SparkConf, SparkContext
from pyspark.mllib.recommendation import ALS
from pyspark.mllib.evaluation import MulticlassMetrics as metric

from machine_learning.movieLens.MovieLens_spark_hcf import spark_inference


def parse_rating(line):
    """
    Parses a rating record in MovieLens format userId::movieId::rating::timestamp .
    """
    fields = line.strip().split("::")
    return int(fields[3]) % 10, (int(fields[0]), int(fields[1]), float(fields[2]))


def parse_movie(line):
    """
    Parses a movie record in MovieLens format movieId::movieTitle .
    """
    fields = line.strip().split("::")
    return int(fields[0]), fields[1]


def load_ratings(ratingsFile):
    """
    Load ratings from file.
    """
    if not isfile(ratingsFile):
        print("File %s does not exist." % ratingsFile)
        sys.exit(1)
    f = open(ratingsFile, 'r')
    ratings = filter(lambda r: r[2] > 0, [parse_rating(line)[1] for line in f])
    f.close()
    if not ratings:
        print("No ratings provided.")
        sys.exit(1)
    else:
        return ratings


def compute_rmse(model, data, n):
    """
    Compute RMSE (Root Mean Squared Error).
    """
    predictions = model.predictAll(data.map(lambda x: (x[0], x[1])))
    predictions_and_ratings = predictions.map(lambda x: ((x[0], x[1]), x[2])) \
        .join(data.map(lambda x: ((x[0], x[1]), x[2]))) \
        .values()
    return sqrt(predictions_and_ratings.map(lambda x: (x[0] - x[1]) ** 2).reduce(add) / float(n))


def main():
    # set up environment
    conf = SparkConf() \
        .setAppName("MovieLensALS") \
        .set("spark.executor.memory", "2g")
    sc = SparkContext(conf=conf)

    # load personal ratings
    path = '../../data/movielens/medium/ratings.dat'
    my_ratings = load_ratings(path)
    my_ratings_rdd = sc.parallelize(my_ratings, 1)

    # load ratings and movie titles

    movie_lens_home_dir = '../../data/movielens/medium/'

    # ratings is an RDD of (last digit of timestamp, (userId, movieId, rating))
    # RDD is Resilient Distributed Dataset
    # UserID::MovieID::Rating::Timestamp
    a = sc.textFile(join(movie_lens_home_dir, "ratings.dat"))
    ratings = sc.textFile(join(movie_lens_home_dir, "ratings.dat")).map(parse_rating)

    # movies is an RDD of (movieId, movieTitle)
    # MovieID::Title::Genres
    movies = dict(sc.textFile(join(movie_lens_home_dir, "movies.dat")).map(parse_movie).collect())

    num_ratings = ratings.count()
    num_users = ratings.values().map(lambda r: r[0]).distinct().count()
    num_movies = ratings.values().map(lambda r: r[1]).distinct().count()

    print("Got %d ratings from %d users on %d movies." % (num_ratings, num_users, num_movies))

    # split ratings into train (60%), validation (20%), and test (20%) based on the
    # last digit of the timestamp, add my_ratings to train, and cache them

    # training, validation, test are all RDDs of (userId, movieId, rating)

    num_partitions = 4
    training = ratings.filter(lambda x: x[0] < 6) \
        .values() \
        .repartition(num_partitions) \
        .cache()

    validation = ratings.filter(lambda x: 6 <= x[0] < 8) \
        .values() \
        .repartition(num_partitions) \
        .cache()

    test = ratings.filter(lambda x: x[0] >= 8).values().cache()

    num_training = training.count()
    num_validation = validation.count()
    num_test = test.count()

    print("Training: %d, validation: %d, test: %d" % (num_training, num_validation, num_test))

    # train models and evaluate them on the validation set

    ranks = [8, 12]
    lambdas = [0.1, 10.0]
    num_iters = [10, 20]
    best_model = None
    best_validation_rmse = float("inf")
    best_validation_auc = float("-inf")
    best_rank = 0
    best_lambda = -1.0
    best_num_iter = -1
    a = training.collect()

    for rank, lmbda, numIter in itertools.product(ranks, lambdas, num_iters):
        model = ALS.train(training, rank, numIter, lmbda)
        validation_rmse = compute_rmse(model, validation, num_validation)
        validation_auroc = spark_inference(model, validation, num_validation)
        # print("RMSE (validation) = %f for the model trained with " % validation_rmse + \
        #       "rank = %d, lambda = %.1f, and numIter = %d." % (rank, lmbda, numIter))
        print("AUROC = {} for the model trained with rank = {}, lambda = {}, and num_iter = "
              "{}".format(validation_auroc, rank, lmbda, numIter))
        if validation_rmse < best_validation_rmse:
            best_model = model
            best_validation_rmse = validation_rmse
            best_rank = rank
            best_lambda = lmbda
            best_num_iter = numIter

    test_rmse = compute_rmse(best_model, test, num_test)

    # evaluate the best model on the test set
    print("The best model was trained with rank = %d and lambda = %.1f, " % (best_rank, best_lambda) \
          + "and numIter = %d, and its RMSE on the test set is %f." % (best_num_iter, test_rmse))

    # compare the best model with a naive baseline that always returns the mean rating
    mean_rating = training.union(validation).map(lambda x: x[2]).mean()
    baseline_rmse = sqrt(test.map(lambda x: (mean_rating - x[2]) ** 2).reduce(add) / num_test)
    improvement = (baseline_rmse - test_rmse) / baseline_rmse * 100
    print("The best model improves the baseline by %.2f" % improvement + "%.")

    # make personalized recommendations

    my_rated_movie_ids = set([x[1] for x in my_ratings])
    candidates = sc.parallelize([m for m in movies if m not in my_rated_movie_ids])
    predictions = best_model.predictAll(candidates.map(lambda x: (0, x))).collect()
    recommendations = sorted(predictions, key=lambda x: x[2], reverse=True)[:50]

    print("Movies recommended for you:")
    for i in range(len(recommendations)):
        print("%2d: %s" % (i + 1, movies[recommendations[i][1]])).encode('ascii', 'ignore')

    # clean up
    sc.stop()


if __name__ == "__main__":
    main()