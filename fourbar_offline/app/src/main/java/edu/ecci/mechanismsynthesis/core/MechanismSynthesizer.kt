package edu.ecci.mechanismsynthesis.core

interface MechanismSynthesizer<S> {
    suspend fun synthesize(curve: List<Vec2>, onProgress: (Float) -> Unit = {}): S
}

sealed interface MechanismSolution {
    val target: List<Vec2>
    val generated: List<Vec2>
    val rmsError: Double
    val maxError: Double
    val quality: String
    val family: String
}

data class FourBarDesign(
    val l1: Double, val l2: Double, val l3: Double, val l4: Double,
    val couplerRadius: Double, val couplerAngle: Double
)

data class FourBarPose(val a: Vec2, val b: Vec2, val c: Vec2, val d: Vec2, val p: Vec2)

data class FourBarSolution(
    val design: FourBarDesign,
    override val target: List<Vec2>,
    override val generated: List<Vec2>,
    val poses: List<FourBarPose>,
    override val rmsError: Double,
    override val maxError: Double,
    val grashof: String,
    override val quality: String
) : MechanismSolution {
    override val family = "Cuatro barras"
}

data class WattIDesign(
    val l0: Double, val l2: Double, val l3: Double, val l4: Double,
    val couplerRadius: Double, val couplerAngle: Double,
    val groundX: Double, val groundY: Double, val l5: Double, val l6: Double,
    val tracerU: Double, val tracerV: Double
)

data class WattIPose(
    val o2: Vec2, val o4: Vec2, val a: Vec2, val b: Vec2,
    val c: Vec2, val d: Vec2, val ground: Vec2, val p: Vec2
)

data class WattISolution(
    val design: WattIDesign,
    override val target: List<Vec2>,
    override val generated: List<Vec2>,
    val poses: List<WattIPose>,
    override val rmsError: Double,
    override val maxError: Double,
    override val quality: String
) : MechanismSolution {
    override val family = "Watt I · seis barras"
}
