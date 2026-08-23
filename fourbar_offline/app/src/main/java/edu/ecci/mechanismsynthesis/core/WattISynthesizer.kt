package edu.ecci.mechanismsynthesis.core

import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.yield
import kotlin.coroutines.coroutineContext
import kotlin.math.*
import kotlin.random.Random

/** Offline Watt-I synthesis derived from the FEF-Graph family model. */
class WattISynthesizer(
    private val particles: Int = 52,
    private val iterations: Int = 210,
    private val samples: Int = 72
) : MechanismSynthesizer<WattISolution> {
    private val lo = doubleArrayOf(35.0,12.0,20.0,20.0,0.0,-PI,-40.0,-90.0,20.0,20.0,-50.0,-80.0)
    private val hi = doubleArrayOf(160.0,95.0,180.0,180.0,150.0,PI,210.0,90.0,180.0,180.0,180.0,80.0)

    override suspend fun synthesize(curve: List<Vec2>, onProgress: (Float) -> Unit): WattISolution {
        val target = FourBarSynthesizer(samples = samples).prepareCurve(curve, samples)
        val rng = Random(target.fold(29) { a, p -> 31 * a + (p.x * 7 + p.y * 3).roundToInt() })
        val x = Array(particles) { feasibleSeed(rng) }
        val velocity = Array(particles) { DoubleArray(12) }
        val personal = Array(particles) { x[it].copyOf() }
        val personalScore = DoubleArray(particles) { evaluate(personal[it], target, 4).score }
        var global = personal[personalScore.indices.minBy { personalScore[it] }].copyOf()
        var globalScore = personalScore.min()

        repeat(iterations) { iteration ->
            coroutineContext.ensureActive()
            val inertia = .88 - .50 * iteration / max(1, iterations - 1).toDouble()
            val radius = 3 + 12 * iteration / max(1, iterations - 1)
            for (i in x.indices) {
                val hood = (i-radius..i+radius).map { (it + particles) % particles }
                val leader = hood.minBy { personalScore[it] }
                for (j in 0..11) {
                    velocity[i][j] = inertia * velocity[i][j] +
                        1.55 * rng.nextDouble() * (personal[i][j] - x[i][j]) +
                        1.85 * rng.nextDouble() * (personal[leader][j] - x[i][j]) +
                        .0015 * (hi[j] - lo[j]) * rng.nextDouble(-1.0, 1.0)
                    x[i][j] = (x[i][j] + velocity[i][j]).coerceIn(lo[j], hi[j])
                }
                var score = evaluate(x[i], target, 4).score
                if (score >= 1e7 && iteration % 18 == 17) {
                    x[i] = feasibleSeed(rng); velocity[i].fill(0.0)
                    score = evaluate(x[i], target, 4).score
                }
                if (score < personalScore[i]) {
                    personalScore[i] = score; personal[i] = x[i].copyOf()
                    if (score < globalScore) { globalScore = score; global = x[i].copyOf() }
                }
            }
            onProgress((iteration + 1f) / iterations)
            yield()
        }

        var best = global.copyOf(); var score = evaluate(best, target, 1).score
        var step = DoubleArray(12) { j -> (hi[j] - lo[j]) * if (j == 5) .025 else .025 }
        repeat(9) {
            for (j in 0..11) for (sign in doubleArrayOf(-1.0, 1.0)) {
                val candidate = best.copyOf(); candidate[j] = (candidate[j] + sign * step[j]).coerceIn(lo[j], hi[j])
                val s = evaluate(candidate, target, 1).score
                if (s < score) { best = candidate; score = s }
            }
            step = DoubleArray(12) { j -> step[j] * .58 }; yield()
        }
        return solution(best, target)
    }

    private data class Fit(val score: Double, val path: List<Vec2> = emptyList(), val shift: Int = 0, val reverse: Boolean = false, val angle: Double = 0.0, val translation: Vec2 = Vec2(0.0,0.0))

    private fun evaluate(x: DoubleArray, target: List<Vec2>, shiftStep: Int): Fit {
        val poses = simulate(design(x), target.size) ?: return Fit(1e8)
        val raw = poses.map { it.p }; var best = Fit(1e8)
        for (reverse in listOf(false, true)) {
            val oriented = if (reverse) raw.reversed() else raw
            for (shift in target.indices step shiftStep) {
                val shifted = List(target.size) { oriented[(it + shift) % oriented.size] }
                val aligned = align(shifted, target)
                val errors = aligned.first.zip(target) { a,b -> a.distance(b) }
                val rms = sqrt(errors.sumOf { it*it } / errors.size); val maxError = errors.max()
                val score = rms + .20 * maxError
                if (score < best.score) best = Fit(score, aligned.first, shift, reverse, aligned.second, aligned.third)
            }
        }
        return best
    }

    private fun solution(x: DoubleArray, target: List<Vec2>): WattISolution {
        val design = design(x); val fit = evaluate(x, target, 1)
        var poses = simulate(design, 180)!!
        if (fit.reverse) poses = poses.reversed()
        poses = List(poses.size) { poses[(it + fit.shift * poses.size / target.size) % poses.size] }
        poses = poses.map { p -> WattIPose(t(p.o2,fit),t(p.o4,fit),t(p.a,fit),t(p.b,fit),t(p.c,fit),t(p.d,fit),t(p.ground,fit),t(p.p,fit)) }
        val errors = fit.path.zip(target) { a,b -> a.distance(b) }
        val rms = sqrt(errors.sumOf { it*it } / errors.size)
        val quality = when { rms<=1.0 -> "Ajuste excelente"; rms<=2.5 -> "Ajuste muy bueno"; rms<=5.0 -> "Ajuste bueno"; else -> "Ajuste aproximado" }
        return WattISolution(design,target,fit.path,poses,rms,errors.max(),quality)
    }

    fun simulate(p: WattIDesign, count: Int): List<WattIPose>? {
        val o2=Vec2(0.0,0.0); val o4=Vec2(p.l0,0.0); val g=Vec2(p.groundX,p.groundY)
        var prevB:Vec2?=null; var prevD:Vec2?=null; val out=ArrayList<WattIPose>(count)
        repeat(count) { i ->
            val th=2*PI*i/count; val a=Vec2(p.l2*cos(th),p.l2*sin(th))
            val bChoices=circles(a,p.l3,o4,p.l4) ?: return null
            val b=prevB?.let { q->bChoices.minBy { it.distance(q) } } ?: bChoices.maxBy { it.y }; prevB=b
            val u=(b-a)*(1.0/p.l3); val v=Vec2(-u.y,u.x)
            val c=a+u*(p.couplerRadius*cos(p.couplerAngle))+v*(p.couplerRadius*sin(p.couplerAngle))
            val dChoices=circles(c,p.l5,g,p.l6) ?: return null
            val d=prevD?.let { q->dChoices.minBy { it.distance(q) } } ?: dChoices.minBy { it.y }; prevD=d
            val u2=(d-c)*(1.0/p.l5); val v2=Vec2(-u2.y,u2.x); val tracer=c+u2*p.tracerU+v2*p.tracerV
            out+=WattIPose(o2,o4,a,b,c,d,g,tracer)
        }
        return out
    }

    private fun feasibleSeed(rng: Random): DoubleArray {
        repeat(900) {
            val x=DoubleArray(12) { j->rng.nextDouble(lo[j],hi[j]) }
            if (simulate(design(x),24)!=null) return x
        }
        return doubleArrayOf(100.0,30.0,85.0,70.0,45.0,.3,100.0,-40.0,130.0,130.0,70.0,20.0)
    }

    private fun design(x:DoubleArray)=WattIDesign(x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8],x[9],x[10],x[11])
    private fun circles(a:Vec2,ra:Double,b:Vec2,rb:Double):List<Vec2>? { val d=b-a; val n=d.norm(); if(n>ra+rb||n<abs(ra-rb)||n<1e-9)return null; val q=(ra*ra-rb*rb+n*n)/(2*n); val h=sqrt(max(0.0,ra*ra-q*q)); val m=a+d*(q/n); val s=Vec2(-d.y/n*h,d.x/n*h); return listOf(m+s,m-s) }
    private fun align(source:List<Vec2>,target:List<Vec2>):Triple<List<Vec2>,Double,Vec2>{ val sc=center(source); val tc=center(target); var c=0.0;var s=0.0; source.indices.forEach{i->val a=source[i]-sc;val b=target[i]-tc;c+=a.x*b.x+a.y*b.y;s+=a.x*b.y-a.y*b.x};val angle=atan2(s,c);val tr=tc-rotate(sc,angle);return Triple(source.map{rotate(it,angle)+tr},angle,tr) }
    private fun center(p:List<Vec2>)=Vec2(p.sumOf{it.x}/p.size,p.sumOf{it.y}/p.size)
    private fun rotate(p:Vec2,a:Double)=Vec2(cos(a)*p.x-sin(a)*p.y,sin(a)*p.x+cos(a)*p.y)
    private fun t(p:Vec2,f:Fit)=rotate(p,f.angle)+f.translation
}

