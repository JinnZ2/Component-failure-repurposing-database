phi = (1 + 5**0.5) / 2
vertices = []
# 8 cube vertices (±1,±1,±1)
for sx in (-1,1):
    for sy in (-1,1):
        for sz in (-1,1):
            vertices.append((sx, sy, sz))
# 24 even permutations of (±φ, ±1/φ, 0)
perms = [(0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)]
signs = [(1,1,1),(1,1,-1),(1,-1,1),(1,-1,-1),(-1,1,1),(-1,1,-1),(-1,-1,1),(-1,-1,-1)]
for p in perms:
    for s in signs:
        v = [0,0,0]
        v[p[0]] = phi * s[0]
        v[p[1]] = (1/phi) * s[1]
        v[p[2]] = 0
        vertices.append(tuple(v))
