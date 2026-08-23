package edu.ecci.mechanismsynthesis.core

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs

class WattISynthesizerTest {
    @Test fun twoLoopsCloseForCompleteRevolution() {
        val design=WattIDesign(100.0,30.0,85.0,70.0,45.0,.3,100.0,-40.0,130.0,130.0,70.0,20.0)
        val poses=WattISynthesizer(particles=3,iterations=2,samples=24).simulate(design,180)
        assertNotNull(poses);assertEquals(180,poses!!.size)
        assertTrue(poses.all{abs(it.o2.distance(it.a)-design.l2)<1e-6})
        assertTrue(poses.all{abs(it.a.distance(it.b)-design.l3)<1e-6})
        assertTrue(poses.all{abs(it.b.distance(it.o4)-design.l4)<1e-6})
        assertTrue(poses.all{abs(it.c.distance(it.d)-design.l5)<1e-6})
        assertTrue(poses.all{abs(it.d.distance(it.ground)-design.l6)<1e-6})
    }
}
