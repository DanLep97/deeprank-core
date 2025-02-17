class VanderwaalsParam:
    def __init__(
            self,
            epsilon_main: float,
            sigma_main: float,
            epsilon_14: float,
            sigma_14: float):
        self.epsilon_main = epsilon_main
        self.sigma_main = sigma_main
        self.epsilon_14 = epsilon_14
        self.sigma_14 = sigma_14
    
    def __str__(self) -> str:
        return f"{self.epsilon_main}, {self.sigma_main}, {self.epsilon_14}, {self.sigma_14}"


class ParamParser:
    @staticmethod
    def parse(file_):
        result = {}
        for line in file_:
            if line.startswith("#"):
                continue

            if line.startswith("NONBonded "):
                (
                    _,
                    type_,
                    epsilon_main,
                    sigma_main,
                    epsilon_14,
                    sigma_14,
                ) = line.split()

                result[type_] = VanderwaalsParam(
                    float(epsilon_main),
                    float(sigma_main),
                    float(epsilon_14),
                    float(sigma_14),
                )
            elif len(line.strip()) == 0:
                continue
            else:
                raise ValueError(f"Unparsable param line: {line}")

        return result
