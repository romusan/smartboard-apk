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
}

