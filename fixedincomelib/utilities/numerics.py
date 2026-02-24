import numpy as np

### 1D Interpolator (only support PIECEWISE_CONSTANT) for now
class Interpolator1D(object):

    def __init__(self, axis, values, method):        
        self.method = method
        self.axis = axis
        self.values = values
        # only supports pwc
        assert method == "PIECEWISE_CONSTANT"
        assert len(self.axis) == len(self.values)

    def interpolate(self, time):

        # left extraplation (flat)
        if time < self.axis[0]:
            return self.values[0]

        # central region
        for i in range(1, len(self.axis)):
            if time >= self.axis[i-1] and time < self.axis[i]:
                return self.values[i]
        
        # right extrapolation
        return self.values[-1]
    
    def integral(self, start, end):
        assert start <= end
        
        # find starting and end index
        startIdx, endIdx = len(self.axis), len(self.axis)
        for i in range(0, len(self.axis)):
            if startIdx == len(self.axis) and start < self.axis[i]:
                startIdx = i
            if end < self.axis[i]:
                endIdx = i
                break
        
        # same block
        if startIdx == endIdx:
            return (end - start) * self.values[-1 if startIdx == len(self.axis) else startIdx]

        # accumulation
        # left
        runningSum = (self.axis[startIdx] - start) * self.values[startIdx]
        # center
        for i in range(startIdx + 1, endIdx):
            runningSum += (self.axis[i] - self.axis[i-1]) * self.values[i]
        # right
        runningSum += (end - self.axis[endIdx - 1]) * self.values[-1 if endIdx == len(self.axis) else endIdx]
        
        return runningSum

class Interpolator2D(object):

    def __init__(
            self,
            axis1: np.ndarray, 
            axis2: np.ndarray, 
            values: np.ndarray, 
            method: str):
        self.method = method
        self.axis1 = axis1
        self.axis2 = axis2
        self.values = values
        assert method == "LINEAR", 'Only LINEAR Supported'
        assert axis1.ndim == 1 and axis2.ndim == 1
        assert values.shape == (len(axis1), len(axis2))

    def interpolate(self, x: float, y: float) -> float:

        x = min(max(x, self.axis1[0]), self.axis1[-1])
        y = min(max(y, self.axis2[0]), self.axis2[-1])

        n1 = len(self.axis1)
        n2 = len(self.axis2)

        # 1x1
        if n1 == 1 and n2 == 1:
            return self.values[0, 0]

        # degenerate axis1 -> linear in y
        if n1 == 1:
            j = int(np.searchsorted(self.axis2, y) - 1)
            j = max(0, min(j, n2 - 2))

            y1, y2 = self.axis2[j], self.axis2[j+1]
            Q11 = self.values[0, j]
            Q12 = self.values[0, j+1]

            if y2 == y1:
                return Q11
            return Q11 + (Q12 - Q11) * (y - y1) / (y2 - y1)

        # degenerate axis2 -> linear in x
        if n2 == 1:
            i = int(np.searchsorted(self.axis1, x) - 1)
            i = max(0, min(i, n1 - 2))

            x1, x2 = self.axis1[i], self.axis1[i+1]
            Q11 = self.values[i, 0]
            Q21 = self.values[i+1, 0]

            if x2 == x1:
                return Q11
            return Q11 + (Q21 - Q11) * (x - x1) / (x2 - x1)

        i = int(np.searchsorted(self.axis1, x) - 1)
        j = int(np.searchsorted(self.axis2, y) - 1)
        i = max(0, min(i, n1 - 2))
        j = max(0, min(j, n2 - 2))

        x1, x2 = self.axis1[i], self.axis1[i+1]
        y1, y2 = self.axis2[j], self.axis2[j+1]
        Q11 = self.values[i,   j]
        Q21 = self.values[i+1, j]
        Q12 = self.values[i,   j+1]
        Q22 = self.values[i+1, j+1]

        if x2 == x1 and y2 == y1:
            return Q11
        elif x2 == x1:
            # linear in y
            return Q11 + (Q12 - Q11) * (y - y1)/(y2 - y1)
        elif y2 == y1:
            # linear in x
            return Q11 + (Q21 - Q11) * (x - x1)/(x2 - x1)

        # bilinear interpolation formula
        return (Q11 * (x2 - x) * (y2 - y) + Q21 * (x - x1) * (y2 - y) + Q12 * (x2 - x) * (y - y1) + Q22 * (x - x1) * (y - y1)) / ((x2 - x1) * (y2 - y1))

    def weights(self, x: float, y: float):
        x = min(max(x, self.axis1[0]), self.axis1[-1])
        y = min(max(y, self.axis2[0]), self.axis2[-1])

        n1 = len(self.axis1)
        n2 = len(self.axis2)

        if n1 == 1 and n2 == 1:
            return [((0, 0), 1.0)]

        # degenerate axis1 -> linear in y
        if n1 == 1:
            j = int(np.searchsorted(self.axis2, y) - 1)
            j = max(0, min(j, n2 - 2))

            y1, y2 = float(self.axis2[j]), float(self.axis2[j+1])
            if y2 == y1:
                return [((0, j), 1.0)]

            ty = (y - y1) / (y2 - y1)
            ty = max(0.0, min(1.0, ty))
            return [((0, j), 1.0 - ty), ((0, j+1), ty)]

        # degenerate axis2 -> linear in x
        if n2 == 1:
            i = int(np.searchsorted(self.axis1, x) - 1)
            i = max(0, min(i, n1 - 2))

            x1, x2 = float(self.axis1[i]), float(self.axis1[i+1])
            if x2 == x1:
                return [((i, 0), 1.0)]

            tx = (x - x1) / (x2 - x1)
            tx = max(0.0, min(1.0, tx))
            return [((i, 0), 1.0 - tx), ((i+1, 0), tx)]

        i = int(np.searchsorted(self.axis1, x) - 1)
        j = int(np.searchsorted(self.axis2, y) - 1)
        i = max(0, min(i, n1 - 2))
        j = max(0, min(j, n2 - 2))

        x1, x2 = float(self.axis1[i]), float(self.axis1[i+1])
        y1, y2 = float(self.axis2[j]), float(self.axis2[j+1])

        if x2 == x1 and y2 == y1:
            return [((i, j), 1.0)]
        if x2 == x1:
            ty = 0.0 if y2 == y1 else (y - y1)/(y2 - y1)
            ty = max(0.0, min(1.0, ty))
            return [((i, j), 1.0 - ty), ((i, j+1), ty)]
        if y2 == y1:
            tx = 0.0 if x2 == x1 else (x - x1)/(x2 - x1)
            tx = max(0.0, min(1.0, tx))
            return [((i, j), 1.0 - tx), ((i+1, j), tx)]

        tx = (x - x1)/(x2 - x1)
        ty = (y - y1)/(y2 - y1)
        tx = max(0.0, min(1.0, tx))
        ty = max(0.0, min(1.0, ty))

        w11 = (1 - tx) * (1 - ty)
        w21 = tx * (1 - ty)
        w12 = (1 - tx) * ty
        w22 = tx * ty

        return [
            ((i, j), w11),
            ((i+1, j), w21),
            ((i, j+1), w12),
            ((i+1, j+1), w22),
        ]
