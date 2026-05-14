"""Worker module for computing initial bone state without Blender (no bpy).
Functions here must be pure Python and pickleable for ProcessPoolExecutor.
"""
from math import sqrt

def _mat_flat_to_rows(mat):
    # mat is a list of 16 floats row-major [m00,m01,m02,m03, m10,...]
    return [mat[0:4], mat[4:8], mat[8:12], mat[12:16]]

def _vec_norm(v):
    return sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])

def _normalize(v):
    n = _vec_norm(v)
    if n == 0:
        return [0.0, 0.0, 0.0]
    return [v[0]/n, v[1]/n, v[2]/n]

def _rotation_matrix_to_quaternion(r):
    # r is 3x3 row-major
    m00, m01, m02 = r[0]
    m10, m11, m12 = r[1]
    m20, m21, m22 = r[2]
    trace = m00 + m11 + m22
    if trace > 0:
        s = 0.5 / sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m21 - m12) * s
        y = (m02 - m20) * s
        z = (m10 - m01) * s
    else:
        if m00 > m11 and m00 > m22:
            s = 2.0 * sqrt(1.0 + m00 - m11 - m22)
            w = (m21 - m12) / s
            x = 0.25 * s
            y = (m01 + m10) / s
            z = (m02 + m20) / s
        elif m11 > m22:
            s = 2.0 * sqrt(1.0 + m11 - m00 - m22)
            w = (m02 - m20) / s
            x = (m01 + m10) / s
            y = 0.25 * s
            z = (m12 + m21) / s
        else:
            s = 2.0 * sqrt(1.0 + m22 - m00 - m11)
            w = (m10 - m01) / s
            x = (m02 + m20) / s
            y = (m12 + m21) / s
            z = 0.25 * s
    return [x, y, z, w]

def compute_initial_state(payload):
    """Compute translation, quaternion rotation, and scale from matrices.
    payload: {'matrix': [16 floats], 'parent_matrix': [16 floats]|None, 'is_additive': bool}
    Returns: {'position':[3], 'rotation':[4], 'scale':[3]}
    """
    mat = payload.get('matrix')
    parent = payload.get('parent_matrix')
    # get world matrix rows
    rows = _mat_flat_to_rows(mat)
    # translation is last column
    tx = rows[0][3]
    ty = rows[1][3]
    tz = rows[2][3]
    # if parent provided, compute local matrix = inv(parent) * mat
    if parent is not None:
        # compute inverse of 4x4 parent (affine)
        prow = _mat_flat_to_rows(parent)
        # extract rotation-scale 3x3 and translation
        p_rot = [prow[0][0:3], prow[1][0:3], prow[2][0:3]]
        p_trans = [prow[0][3], prow[1][3], prow[2][3]]
        # inverse rotation-scale is inverse of 3x3
        # compute determinant and inverse (explicit formula)
        a,b,c = p_rot[0]
        d,e,f = p_rot[1]
        g,h,i = p_rot[2]
        det = a*(e*i - f*h) - b*(d*i - f*g) + c*(d*h - e*g)
        if abs(det) < 1e-9:
            inv3 = [[1,0,0],[0,1,0],[0,0,1]]
        else:
            invdet = 1.0/det
            inv3 = [
                [(e*i - f*h)*invdet, (c*h - b*i)*invdet, (b*f - c*e)*invdet],
                [(f*g - d*i)*invdet, (a*i - c*g)*invdet, (c*d - a*f)*invdet],
                [(d*h - e*g)*invdet, (b*g - a*h)*invdet, (a*e - b*d)*invdet]
            ]
        # compute local 3x3 = inv3 * rot3
        rot3 = [rows[0][0:3], rows[1][0:3], rows[2][0:3]]
        local3 = [[0.0]*3 for _ in range(3)]
        for r in range(3):
            for c2 in range(3):
                local3[r][c2] = inv3[r][0]*rot3[0][c2] + inv3[r][1]*rot3[1][c2] + inv3[r][2]*rot3[2][c2]
        local_tx = tx - (p_trans[0] + 0)
        local_ty = ty - (p_trans[1] + 0)
        local_tz = tz - (p_trans[2] + 0)
        # compute scales from columns of local3
        col0 = [local3[0][0], local3[1][0], local3[2][0]]
        col1 = [local3[0][1], local3[1][1], local3[2][1]]
        col2 = [local3[0][2], local3[1][2], local3[2][2]]
        sx = _vec_norm(col0)
        sy = _vec_norm(col1)
        sz = _vec_norm(col2)
        # normalize rotation matrix
        if sx != 0: col0 = [c/sx for c in col0]
        if sy != 0: col1 = [c/sy for c in col1]
        if sz != 0: col2 = [c/sz for c in col2]
        rot_mat = [[col0[0], col1[0], col2[0]],[col0[1], col1[1], col2[1]],[col0[2], col1[2], col2[2]]]
        quat = _rotation_matrix_to_quaternion(rot_mat)
        position = [local_tx, local_ty, local_tz]
        scale = [sx, sy, sz]
    else:
        # world-local equals matrix components
        col0 = [rows[0][0], rows[1][0], rows[2][0]]
        col1 = [rows[0][1], rows[1][1], rows[2][1]]
        col2 = [rows[0][2], rows[1][2], rows[2][2]]
        sx = _vec_norm(col0)
        sy = _vec_norm(col1)
        sz = _vec_norm(col2)
        if sx != 0: col0 = [c/sx for c in col0]
        if sy != 0: col1 = [c/sy for c in col1]
        if sz != 0: col2 = [c/sz for c in col2]
        rot_mat = [[col0[0], col1[0], col2[0]],[col0[1], col1[1], col2[1]],[col0[2], col1[2], col2[2]]]
        quat = _rotation_matrix_to_quaternion(rot_mat)
        position = [tx, ty, tz]
        scale = [sx, sy, sz]
    # For additive animations, scale may be treated differently by consumer; keep as-is
    return {'position': position, 'rotation': quat, 'scale': scale}
