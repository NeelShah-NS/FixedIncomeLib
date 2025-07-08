
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

