"""User-selected educational guidance, not automatic physical identification."""

TEMPLATES = {
    "Ohm's law": {"x": "current I (A)", "y": "voltage V (V)", "model": "V = R I + b (linear approximation)",
                    "parameters": "Slope may estimate resistance in ohms only when the mapping and units are confirmed.",
                    "assumptions": "Approximately Ohmic behavior over the measured range; conditions and calibration must be assessed."},
    "Simple pendulum": {"x": "length L (m)", "y": "period T (s)", "model": "T = 2 pi sqrt(L/g) under a small-angle model",
                        "parameters": "The slope of T squared versus L is 4 pi squared / g if the assumptions hold.",
                        "assumptions": "Small amplitude, negligible damping, suitable pendulum geometry; explicitly calculate T squared outside this guidance."},
    "Hooke's law": {"x": "extension x (m)", "y": "force F (N)", "model": "F = k x + b (linear approximation)",
                      "parameters": "Slope may estimate spring stiffness in N/m with confirmed roles and units.",
                      "assumptions": "Elastic linear range, equilibrium and calibration; offsets may have several causes."},
    "Newton's cooling law": {"x": "time t (s)", "y": "temperature T (degrees)", "model": "T = T_ambient + A exp(-k t)",
                              "parameters": "k is a conditional cooling rate; its interpretation depends on units and the fitted model.",
                              "assumptions": "Approximately constant ambient temperature and a lumped thermal model; assess sensor response and conditions."},
    "Linear thermal expansion": {"x": "temperature change ΔT", "y": "length change ΔL", "model": "ΔL = alpha L0 ΔT (linear approximation)",
                                 "parameters": "Slope divided by independently supplied initial length L0 can estimate alpha; no L0 is inferred.",
                                 "assumptions": "Small temperature range, appropriate material and stable reference length; calibration matters."},
}
