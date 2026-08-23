package edu.ecci.mechanismsynthesis.core

import kotlin.math.hypot

data class Vec2(val x: Double, val y: Double) {
    operator fun plus(o: Vec2) = Vec2(x + o.x, y + o.y)
    operator fun minus(o: Vec2) = Vec2(x - o.x, y - o.y)
    operator fun times(k: Double) = Vec2(x * k, y * k)
    fun norm() = hypot(x, y)
    fun distance(o: Vec2) = (this - o).norm()
}

