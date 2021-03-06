# Copyright 2018 The TensorFlow Probability Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Tests for the unconstrained L-BFGS optimizer."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools
import numpy as np
from scipy.stats import special_ortho_group

import tensorflow.compat.v1 as tf1
import tensorflow.compat.v2 as tf
import tensorflow_probability as tfp

from tensorflow_probability.python.internal import test_util


def _make_val_and_grad_fn(value_fn):
  @functools.wraps(value_fn)
  def val_and_grad(x):
    return tfp.math.value_and_gradient(value_fn, x)
  return val_and_grad


def _norm(x):
  return np.linalg.norm(x, np.inf)


@test_util.test_all_tf_execution_regimes
class LBfgsTest(test_util.TestCase):
  """Tests for LBFGS optimization algorithm."""

  def test_quadratic_bowl_2d(self):
    """Can minimize a two dimensional quadratic function."""
    minimum = np.array([1.0, 1.0])
    scales = np.array([2.0, 3.0])

    @_make_val_and_grad_fn
    def quadratic(x):
      return tf.reduce_sum(input_tensor=scales * (x - minimum)**2)

    start = tf.constant([0.6, 0.8])
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        quadratic, initial_position=start, tolerance=1e-8))
    self.assertTrue(results.converged)
    self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
    self.assertArrayNear(results.position, minimum, 1e-5)

  def test_high_dims_quadratic_bowl_trivial(self):
    """Can minimize a high-dimensional trivial bowl (sphere)."""
    ndims = 100
    minimum = np.ones([ndims], dtype='float64')
    scales = np.ones([ndims], dtype='float64')

    @_make_val_and_grad_fn
    def quadratic(x):
      return tf.reduce_sum(input_tensor=scales * (x - minimum)**2)

    start = np.zeros([ndims], dtype='float64')
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        quadratic, initial_position=start, tolerance=1e-8))
    self.assertTrue(results.converged)
    self.assertEqual(results.num_iterations, 1)  # Solved by first line search.
    self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
    self.assertArrayNear(results.position, minimum, 1e-5)

  def test_quadratic_bowl_40d(self):
    """Can minimize a high-dimensional quadratic function."""
    dim = 40
    np.random.seed(14159)
    minimum = np.random.randn(dim)
    scales = np.exp(np.random.randn(dim))

    @_make_val_and_grad_fn
    def quadratic(x):
      return tf.reduce_sum(input_tensor=scales * (x - minimum)**2)

    start = tf.ones_like(minimum)
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        quadratic, initial_position=start, tolerance=1e-8))
    self.assertTrue(results.converged)
    self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
    self.assertArrayNear(results.position, minimum, 1e-5)

  def test_quadratic_with_skew(self):
    """Can minimize a general quadratic function."""
    dim = 50
    np.random.seed(26535)
    minimum = np.random.randn(dim)
    principal_values = np.diag(np.exp(np.random.randn(dim)))
    rotation = special_ortho_group.rvs(dim)
    hessian = np.dot(np.transpose(rotation), np.dot(principal_values, rotation))

    @_make_val_and_grad_fn
    def quadratic(x):
      y = x - minimum
      yp = tf.tensordot(hessian, y, axes=[1, 0])
      return tf.reduce_sum(input_tensor=y * yp) / 2

    start = tf.ones_like(minimum)
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        quadratic, initial_position=start, tolerance=1e-8))
    self.assertTrue(results.converged)
    self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
    self.assertArrayNear(results.position, minimum, 1e-5)

  def test_quadratic_with_strong_skew(self):
    """Can minimize a strongly skewed quadratic function."""
    np.random.seed(89793)
    minimum = np.random.randn(3)
    principal_values = np.diag(np.array([0.1, 2.0, 50.0]))
    rotation = special_ortho_group.rvs(3)
    hessian = np.dot(np.transpose(rotation), np.dot(principal_values, rotation))

    @_make_val_and_grad_fn
    def quadratic(x):
      y = x - minimum
      yp = tf.tensordot(hessian, y, axes=[1, 0])
      return tf.reduce_sum(input_tensor=y * yp) / 2

    start = tf.ones_like(minimum)
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        quadratic, initial_position=start, tolerance=1e-8))
    self.assertTrue(results.converged)
    self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
    self.assertArrayNear(results.position, minimum, 1e-5)

  def test_rosenbrock_2d(self):
    """Tests L-BFGS on the Rosenbrock function.

    The Rosenbrock function is a standard optimization test case. In two
    dimensions, the function is (a, b > 0):
      f(x, y) = (a - x)^2 + b (y - x^2)^2
    The function has a global minimum at (a, a^2). This minimum lies inside
    a parabolic valley (y = x^2).
    """
    def rosenbrock(coord):
      """The Rosenbrock function in two dimensions with a=1, b=100.

      Args:
        coord: A Tensor of shape [2]. The coordinate of the point to evaluate
          the function at.

      Returns:
        fv: A scalar tensor containing the value of the Rosenbrock function at
          the supplied point.
        dfx: Scalar tensor. The derivative of the function with respect to x.
        dfy: Scalar tensor. The derivative of the function with respect to y.
      """
      x, y = coord[0], coord[1]
      fv = (1 - x)**2 + 100 * (y - x**2)**2
      dfx = 2 * (x - 1) + 400 * x * (x**2 - y)
      dfy = 200 * (y - x**2)
      return fv, tf.stack([dfx, dfy])

    start = tf.constant([-1.2, 1.0])
    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        rosenbrock, initial_position=start, tolerance=1e-5))
    self.assertTrue(results.converged)
    self.assertTrue(_norm(results.objective_gradient) <= 1e-5)
    self.assertArrayNear(results.position, np.array([1.0, 1.0]), 1e-5)

  def test_himmelblau(self):
    """Tests minimization on the Himmelblau's function.

    Himmelblau's function is a standard optimization test case. The function is
    given by:

      f(x, y) = (x^2 + y - 11)^2 + (x + y^2 - 7)^2

    The function has four minima located at (3, 2), (-2.805118, 3.131312),
    (-3.779310, -3.283186), (3.584428, -1.848126).

    All these minima may be reached from appropriate starting points. To keep
    the runtime of this test small, here we only find the first two minima.
    However, all four can be easily found in `test_himmelblau_batch_all` below
    with the help of batching.
    """
    @_make_val_and_grad_fn
    def himmelblau(coord):
      x, y = coord[0], coord[1]
      return (x * x + y - 11) ** 2 + (x + y * y - 7) ** 2

    starts_and_targets = [
        # Start Point, Target Minimum, Num evaluations expected.
        [(1, 1), (3, 2), 31],
        [(-2, 2), (-2.805118, 3.131312), 17],
    ]
    dtype = 'float64'
    for start, expected_minima, expected_evals in starts_and_targets:
      start = tf.constant(start, dtype=dtype)
      results = self.evaluate(tfp.optimizer.lbfgs_minimize(
          himmelblau, initial_position=start, tolerance=1e-8))
      self.assertTrue(results.converged)
      self.assertArrayNear(results.position,
                           np.array(expected_minima, dtype=dtype),
                           1e-5)
      self.assertEqual(results.num_objective_evaluations, expected_evals)

  def test_himmelblau_batch_all(self):
    @_make_val_and_grad_fn
    def himmelblau(coord):
      x, y = coord[..., 0], coord[..., 1]
      return (x * x + y - 11) ** 2 + (x + y * y - 7) ** 2

    dtype = 'float64'
    starts = tf.constant([[1, 1],
                          [-2, 2],
                          [-1, -1],
                          [1, -2]], dtype=dtype)
    expected_minima = np.array([[3, 2],
                                [-2.805118, 3.131312],
                                [-3.779310, -3.283186],
                                [3.584428, -1.848126]], dtype=dtype)
    batch_results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        himmelblau, initial_position=starts,
        stopping_condition=tfp.optimizer.converged_all, tolerance=1e-8))

    self.assertFalse(np.any(batch_results.failed))  # None have failed.
    self.assertTrue(np.all(batch_results.converged))  # All converged.

    # All converged points are near expected minima.
    for actual, expected in zip(batch_results.position, expected_minima):
      self.assertArrayNear(actual, expected, 1e-5)
    self.assertEqual(batch_results.num_objective_evaluations, 36)

  def test_himmelblau_batch_any(self):
    @_make_val_and_grad_fn
    def himmelblau(coord):
      x, y = coord[..., 0], coord[..., 1]
      return (x * x + y - 11) ** 2 + (x + y * y - 7) ** 2

    dtype = 'float64'
    starts = tf.constant([[1, 1],
                          [-2, 2],
                          [-1, -1],
                          [1, -2]], dtype=dtype)
    expected_minima = np.array([[3, 2],
                                [-2.805118, 3.131312],
                                [-3.779310, -3.283186],
                                [3.584428, -1.848126]], dtype=dtype)

    # Run with `converged_any` stopping condition, to stop as soon as any of
    # the batch members have converged.
    batch_results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        himmelblau, initial_position=starts,
        stopping_condition=tfp.optimizer.converged_any, tolerance=1e-8))

    self.assertFalse(np.any(batch_results.failed))  # None have failed.
    self.assertTrue(np.any(batch_results.converged))  # At least one converged.
    self.assertFalse(np.all(batch_results.converged))  # But not all did.

    # Converged points are near expected minima.
    for actual, expected in zip(batch_results.position[batch_results.converged],
                                expected_minima[batch_results.converged]):
      self.assertArrayNear(actual, expected, 1e-5)
    self.assertEqual(batch_results.num_objective_evaluations, 28)

  def test_data_fitting(self):
    """Tests MLE estimation for a simple geometric GLM."""
    n, dim = 100, 30
    dtype = tf.float64
    np.random.seed(234095)
    x = np.random.choice([0, 1], size=[dim, n])
    s = 0.01 * np.sum(x, 0)
    p = 1. / (1 + np.exp(-s))
    y = np.random.geometric(p)
    x_data = tf.convert_to_tensor(value=x, dtype=dtype)
    y_data = tf.expand_dims(tf.convert_to_tensor(value=y, dtype=dtype), -1)

    @_make_val_and_grad_fn
    def neg_log_likelihood(state):
      state_ext = tf.expand_dims(state, 0)
      linear_part = tf.matmul(state_ext, x_data)
      linear_part_ex = tf.stack([tf.zeros_like(linear_part),
                                 linear_part], axis=0)
      term1 = tf.squeeze(
          tf.matmul(
              tf.reduce_logsumexp(input_tensor=linear_part_ex, axis=0), y_data),
          -1)
      term2 = (
          0.5 * tf.reduce_sum(input_tensor=state_ext * state_ext, axis=-1) -
          tf.reduce_sum(input_tensor=linear_part, axis=-1))
      return  tf.squeeze(term1 + term2)

    start = tf.ones(shape=[dim], dtype=dtype)

    results = self.evaluate(tfp.optimizer.lbfgs_minimize(
        neg_log_likelihood, initial_position=start, tolerance=1e-6))
    self.assertTrue(results.converged)

  def test_determinism(self):
    """Tests that the results are determinsitic."""
    dim = 25

    @_make_val_and_grad_fn
    def rastrigin(x):
      """The value and gradient of the Rastrigin function.

      The Rastrigin function is a standard optimization test case. It is a
      multimodal non-convex function. While it has a large number of local
      minima, the global minimum is located at the origin and where the function
      value is zero. The standard search domain for optimization problems is the
      hypercube [-5.12, 5.12]**d in d-dimensions.

      Args:
        x: Real `Tensor` of shape [2]. The position at which to evaluate the
          function.

      Returns:
        value_and_gradient: A tuple of two `Tensor`s containing
          value: A scalar `Tensor` of the function value at the supplied point.
          gradient: A `Tensor` of shape [2] containing the gradient of the
            function along the two axes.
      """
      return tf.reduce_sum(input_tensor=x**2 -
                           10.0 * tf.cos(2 * np.pi * x)) + 10.0 * dim

    start_position = np.random.rand(dim) * 2.0 * 5.12 - 5.12

    def get_results():
      start = tf.constant(start_position)
      return self.evaluate(tfp.optimizer.lbfgs_minimize(
          rastrigin, initial_position=start, tolerance=1e-5))

    res1, res2 = get_results(), get_results()

    self.assertTrue(res1.converged)
    self.assertEqual(res1.converged, res2.converged)
    self.assertEqual(res1.failed, res2.failed)
    self.assertEqual(res1.num_objective_evaluations,
                     res2.num_objective_evaluations)
    self.assertArrayNear(res1.position, res2.position, 1e-5)
    self.assertAlmostEqual(res1.objective_value, res2.objective_value)
    self.assertArrayNear(res1.objective_gradient, res2.objective_gradient, 1e-5)
    self.assertArrayNear(res1.position_deltas.reshape([-1]),
                         res2.position_deltas.reshape([-1]), 1e-5)
    self.assertArrayNear(res1.gradient_deltas.reshape([-1]),
                         res2.gradient_deltas.reshape([-1]), 1e-5)

  def test_dynamic_shapes(self):
    """Can build an lbfgs_op with dynamic shapes in graph mode."""
    if tf.executing_eagerly(): return
    ndims = 60
    minimum = np.ones([ndims], dtype='float64')
    scales = np.arange(ndims, dtype='float64') + minimum

    @_make_val_and_grad_fn
    def quadratic(x):
      return tf.reduce_sum(input_tensor=scales * (x - minimum)**2)

    # Test with a vector of unknown dimension, and a fully unknown shape.
    for shape in ([None], None):
      start = tf1.placeholder(tf.float32, shape=shape)
      lbfgs_op = tfp.optimizer.lbfgs_minimize(
          quadratic, initial_position=start, tolerance=1e-8)
      self.assertFalse(lbfgs_op.position.shape.is_fully_defined())

      start_value = np.arange(ndims, 0, -1, dtype='float64')
      with self.cached_session() as session:
        results = session.run(lbfgs_op, feed_dict={start: start_value})
      self.assertTrue(results.converged)
      self.assertTrue(_norm(results.objective_gradient) <= 1e-8)
      self.assertArrayNear(results.position, minimum, 1e-5)


if __name__ == '__main__':
  tf.test.main()
