package edu.ecci.mechanismsynthesis.core

import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.yield
import kotlin.coroutines.coroutineContext
import kotlin.math.*
import kotlin.random.Random

class FourBarSynthesizer(
    private val particles: Int = 42,
    private val iterations: Int = 150,
    private val samples: Int = 64
) : MechanismSynthesizer<FourBarSolution> {
    private val lower = doubleArrayOf(50.0, 15.0, 50.0, 30.0, 15.0, -PI)
    private val upper = doubleArrayOf(120.0, 55.0, 110.0, 80.0, 55.0, PI)

    override suspend fun synthesize(curve: List<Vec2>, onProgress: (Float) -> Unit): FourBarSolution {
        require(curve.size >= 8) { "La curva necesita al menos 8 puntos" }
        val target = normalizeAndResample(curve, samples)
        val rng = Random(target.fold(17) { a, p -> 31 * a + (p.x * 10 + p.y).roundToInt() })
        val pos = Array(particles) { DoubleArray(6) { j -> rng.nextDouble(lower[j], upper[j]) } }
        val vel = Array(particles) { DoubleArray(6) }
        val best = Array(particles) { pos[it].copyOf() }
        val bestScore = DoubleArray(particles) { evaluate(best[it], target).score }
        var global = best[bestScore.indices.minBy { bestScore[it] }].copyOf()
        var globalScore = bestScore.min()

        repeat(iterations) { step ->
            coroutineContext.ensureActive()
            val inertia = 0.90 - 0.55 * step / max(1, iterations - 1).toDouble()
            val radius = 3 + (13 * step / max(1, iterations - 1))
            for (i in 0 until particles) {
                val neighborhood = (i - radius..i + radius).map { (it + particles) % particles }
                val localIndex = neighborhood.minBy { bestScore[it] }
                for (j in 0..5) {
                    val cognition = 1.65 * rng.nextDouble() * (best[i][j] - pos[i][j])
                    val social = 1.80 * rng.nextDouble() * (best[localIndex][j] - pos[i][j])
                    val jitter = (upper[j] - lower[j]) * 0.002 * rng.nextDouble(-1.0, 1.0)
                    vel[i][j] = inertia * vel[i][j] + cognition + social + jitter
                    pos[i][j] = (pos[i][j] + vel[i][j]).coerceIn(lower[j], upper[j])
                }
                val score = evaluate(pos[i], target).score
                if (score < bestScore[i]) {
                    bestScore[i] = score
                    best[i] = pos[i].copyOf()
                    if (score < globalScore) { globalScore = score; global = pos[i].copyOf() }
                }
            }
            onProgress((step + 1f) / iterations)
            yield()
        }
        return buildSolution(global, target)
    }

    private data class Evaluation(val score: Double, val aligned: List<Vec2> = emptyList(), val shift: Int = 0, val angle: Double = 0.0, val translation: Vec2 = Vec2(0.0, 0.0))

    private fun evaluate(x: DoubleArray, target: List<Vec2>): Evaluation {
        val design = FourBarDesign(x[0], x[1], x[2], x[3], x[4], x[5])
        val poses = mechanismPoses(design, target.size) ?: return Evaluation(1e8)
        val raw = poses.map { it.p }
        var answer = Evaluation(1e8)
        for (shift in target.indices step 2) {
            val shifted = List(target.size) { raw[(it + shift) % raw.size] }
            val fit = align(shifted, target)
            val errors = fit.first.zip(target) { a, b -> a.distance(b) }
            val rms = sqrt(errors.sumOf { it * it } / errors.size)
            val maxError = errors.max()
            val singular = poses.count { abs(cross(it.c - it.b, it.d - it.c)) < 25.0 }.toDouble() / poses.size
            val complexity = .002 * x.take(5).sum()
            val score = rms + .30 * maxError + 10.0 * singular + complexity
            if (score < answer.score) answer = Evaluation(score, fit.first, shift, fit.second, fit.third)
        }
        return answer
    }

    private fun buildSolution(x: DoubleArray, target: List<Vec2>): FourBarSolution {
        val d = FourBarDesign(x[0], x[1], x[2], x[3], x[4], x[5])
        val evaluation = evaluate(x, target)
        val rawPoses = mechanismPoses(d, 180)!!
        val alignedPoses = rawPoses.map { pose ->
            FourBarPose(transform(pose.a, evaluation.angle, evaluation.translation), transform(pose.b, evaluation.angle, evaluation.translation), transform(pose.c, evaluation.angle, evaluation.translation), transform(pose.d, evaluation.angle, evaluation.translation), transform(pose.p, evaluation.angle, evaluation.translation))
        }
        val errors = evaluation.aligned.zip(target) { a, b -> a.distance(b) }
        val links = listOf(d.l1, d.l2, d.l3, d.l4).sorted()
        val grashof = if (links.first() + links.last() <= links[1] + links[2]) "Grashof: rotación completa" else "No Grashof: movimiento oscilante"
        return FourBarSolution(d, target, evaluation.aligned, alignedPoses, sqrt(errors.sumOf { it * it } / errors.size), errors.max(), grashof)
    }

    fun mechanismPoses(d: FourBarDesign, count: Int): List<FourBarPose>? {
        val result = ArrayList<FourBarPose>(count)
        var previous: Vec2? = null
        repeat(count) { i ->
            val theta = 2.0 * PI * i / count
            val a = Vec2(0.0, 0.0); val fixed = Vec2(d.l1, 0.0)
            val b = Vec2(d.l2 * cos(theta), d.l2 * sin(theta))
            val intersections = circleIntersections(b, d.l3, fixed, d.l4) ?: return@repeat
            val c = previous?.let { p -> intersections.minBy { it.distance(p) } } ?: intersections.maxBy { it.y }
            previous = c
            val u = (c - b) * (1.0 / d.l3); val v = Vec2(-u.y, u.x)
            val p = b + u * (d.couplerRadius * cos(d.couplerAngle)) + v * (d.couplerRadius * sin(d.couplerAngle))
            result += FourBarPose(a, b, c, fixed, p)
        }
        return result.takeIf { it.size >= count * 0.85 }
    }

    private fun circleIntersections(p0: Vec2, r0: Double, p1: Vec2, r1: Double): List<Vec2>? {
        val delta = p1 - p0; val distance = delta.norm()
        if (distance > r0 + r1 || distance < abs(r0 - r1) || distance < 1e-9) return null
        val a = (r0 * r0 - r1 * r1 + distance * distance) / (2 * distance)
        val h = sqrt(max(0.0, r0 * r0 - a * a)); val mid = p0 + delta * (a / distance)
        val side = Vec2(-delta.y / distance * h, delta.x / distance * h)
        return listOf(mid + side, mid - side)
    }

    private fun align(source: List<Vec2>, target: List<Vec2>): Triple<List<Vec2>, Double, Vec2> {
        val sc = centroid(source); val tc = centroid(target)
        var c = 0.0; var s = 0.0
        source.indices.forEach { i ->
            val a = source[i] - sc; val b = target[i] - tc
            c += a.x * b.x + a.y * b.y; s += a.x * b.y - a.y * b.x
        }
        val angle = atan2(s, c); val translation = tc - rotate(sc, angle)
        return Triple(source.map { transform(it, angle, translation) }, angle, translation)
    }

    private fun normalizeAndResample(points: List<Vec2>, n: Int): List<Vec2> {
        val closed = if (points.first().distance(points.last()) < 2.0) points else points + points.first()
        val lengths = closed.zipWithNext { a, b -> a.distance(b) }
        val total = lengths.sum(); require(total > 20.0) { "Dibuja una curva más grande" }
        val sampled = (0 until n).map { k ->
            val distance = total * k / n; var accumulated = 0.0; var index = 0
            while (index < lengths.lastIndex && accumulated + lengths[index] < distance) { accumulated += lengths[index]; index++ }
            val t = ((distance - accumulated) / lengths[index]).coerceIn(0.0, 1.0)
            closed[index] + (closed[index + 1] - closed[index]) * t
        }
        val center = centroid(sampled)
        val width = sampled.maxOf { it.x } - sampled.minOf { it.x }
        val height = sampled.maxOf { it.y } - sampled.minOf { it.y }
        val scale = 100.0 / max(width, height).coerceAtLeast(1.0)
        return sampled.map { (it - center) * scale }
    }

    private fun centroid(points: List<Vec2>) = Vec2(points.sumOf { it.x } / points.size, points.sumOf { it.y } / points.size)
    private fun rotate(p: Vec2, a: Double) = Vec2(cos(a) * p.x - sin(a) * p.y, sin(a) * p.x + cos(a) * p.y)
    private fun transform(p: Vec2, a: Double, t: Vec2) = rotate(p, a) + t
    private fun cross(a: Vec2, b: Vec2) = a.x * b.y - a.y * b.x
}

