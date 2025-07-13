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

        # --- find surrounding indices ---
        i = np.searchsorted(self.axis1, x) - 1
        j = np.searchsorted(self.axis2, y) - 1
        # handle exact right edge
        if i == len(self.axis1) - 1:
            i -= 1
        if j == len(self.axis2) - 1:
            j -= 1

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

        # --- bilinear interpolation formula ---
        return (Q11 * (x2 - x) * (y2 - y) + Q21 * (x - x1) * (y2 - y) + Q12 * (x2 - x) * (y - y1) + Q22 * (x - x1) * (y - y1)) / ((x2 - x1) * (y2 - y1))