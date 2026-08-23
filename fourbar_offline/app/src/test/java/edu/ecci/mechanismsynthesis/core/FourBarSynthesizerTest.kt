package edu.ecci.mechanismsynthesis.core

import org.junit.Assert.*
import org.junit.Test

class FourBarSynthesizerTest {
    @Test fun forwardKinematicsProducesContinuousClosedCycle() {
        val poses = FourBarSynthesizer(particles = 4, iterations = 2).mechanismPoses(
            FourBarDesign(100.0, 30.0, 80.0, 70.0, 35.0, 0.45), 180
        )
        assertNotNull(poses)
        assertEquals(180, poses!!.size)
        assertTrue(poses.all { it.a.distance(it.b).let { length -> length in 29.999..30.001 } })
        assertTrue(poses.all { it.b.distance(it.c).let { length -> length in 79.999..80.001 } })
        assertTrue(poses.all { it.c.distance(it.d).let { length -> length in 69.999..70.001 } })
        assertTrue(poses.first().p.distance(poses.last().p) < 5.0)
    }

    @Test fun repeatedPenSamplesDoNotProduceNaN() {
        val curve = buildList {
            repeat(24) { i ->
                val angle = 2.0 * Math.PI * i / 24
                val point = Vec2(200.0 + 100.0 * kotlin.math.cos(angle), 160.0 + 70.0 * kotlin.math.sin(angle))
                add(point)
                add(point) // Typical stationary S Pen duplicate.
            }
        }
        val normalized = FourBarSynthesizer(samples = 24).prepareCurve(curve, 24)
        assertEquals(24, normalized.size)
        assertTrue(normalized.all { it.x.isFinite() && it.y.isFinite() })
    }
}
