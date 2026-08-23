package edu.ecci.mechanismsynthesis.core

interface MechanismSynthesizer<S> {
    suspend fun synthesize(curve: List<Vec2>, onProgress: (Float) -> Unit = {}): S
}

data class FourBarDesign(
    val l1: Double, val l2: Double, val l3: Double, val l4: Double,
    val couplerRadius: Double, val couplerAngle: Double
)

data class FourBarPose(val a: Vec2, val b: Vec2, val c: Vec2, val d: Vec2, val p: Vec2)

data class FourBarSolution(
    val design: FourBarDesign,
    val target: List<Vec2>,
    val generated: List<Vec2>,
    val poses: List<FourBarPose>,
    val rmsError: Double,
    val maxError: Double,
    val grashof: String,
    val quality: String
)
