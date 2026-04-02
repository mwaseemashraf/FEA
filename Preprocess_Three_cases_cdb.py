import os
import numpy as np
import pyvista as pv
from fortranformat import FortranRecordWriter

# Provide user inputs
######################################################################################################
Input_file_type = 'cdb'   # 'cdb' or 'vtk'
base_dir = './'
fn = 'Synthetic'          # base filename, expects Synthetic.vtk for grain/Euler metadata
output_name = 'MatAssign'

# Choose one:
# 'elastic'
# 'isotropic_hardening'
# 'crystal_plasticity'
MaterialModel = 'elastic'

# vtk metadata options
scale_factor = 1.0 / 50.0
EulerAngleKey = 'EulerAngles'
GrainKey = 'FeatureIds'

# Ansys expects Euler angles in degrees and in Z-X-Z order
def FormatEA(my_ea):
    phi1 = my_ea[0] / np.pi * 180.0 - 180.0
    phi = 0.0
    phi2 = 0.0
    return [phi1, phi, phi2]

# Elastic behavior
Elastic_type = 'CUBIC'

# Isotropic elasticity inputs used to construct cubic-equivalent constants
E = 70000
pr = 0.38
C11 = E * (1 - pr) / (1 - pr - 2 * pr * pr)
C12 = E * pr / (1 - pr - 2 * pr * pr)
C44 = E / (2.0 * (1 + pr))
Elastic_constants = [C11, C12, C44]

# Thermomechanical behavior
CTE = 1.28e-05

# Isotropic hardening parameters
YieldStress = 220.0
TangentModulus = 1750.0

# Crystal plasticity parameters
CrystalType = 'FCC'
ini_hardness = 220.0
hardening_modulus = 1750.0
sat_hardness = 400.0
r = 2
n_ = 0
T_ref = 298.0
latent_hardening_ratio = 1.4
gamma_dot_0 = 1732000.0
Q_s = 2.5e-19
p = 0.131
q = 1.1
m = 0.005
thermal_athermal_ratio = 0.7
C_2_A_ratio = 1
######################################################################################################

CrystalMap = {'FCC': 1, 'HCP': 2, 'BCC': 3}
CryType = CrystalMap[CrystalType]

if CryType == 1:  # FCC
    nSS = 12
    nSF = 1
    flow_paras = [gamma_dot_0, p, q, thermal_athermal_ratio, Q_s, C_2_A_ratio]
    formulation = 2
elif CryType == 2:  # HCP
    nSS = 30
    nSF = 5
    flow_paras = [gamma_dot_0, m, C_2_A_ratio]
    formulation = 1
elif CryType == 3:  # BCC
    nSS = 48
    nSF = 3
    flow_paras = [gamma_dot_0, p, q, thermal_athermal_ratio, Q_s, C_2_A_ratio]
    formulation = 2
else:
    raise ValueError(f"Unsupported CrystalType: {CrystalType}")


def vtk2cdb(vtk, output_name):
    content = (
        "/COM,ANSYS RELEASE 2023 R2\n"
        "/PREP7\n"
        "ETBLOCK,        1,        1\n"
        "(2i9,19a9)\n"
        "        1      185        0        0        0        0        0        0        0        0        0        0        0        0        0        0        0        0        0        0        0\n"
        "       -1\n"
    )

    nodes = vtk.points
    fmt = "%10s,%10s"
    content += "NBLOCK,6,SOLID," + (fmt % (len(nodes), len(nodes))) + "\n"
    content += "(3i9,6e21.13e3)\n"

    line = FortranRecordWriter('(3i9,6e21.13e3)')
    for i, n in enumerate(nodes):
        content += line.write([i + 1, 0, 0, n[0], n[1], n[2]]) + '\n'
    content += 'N,UNBL,LOC,       -1,\n'

    assert vtk.get_cell(0).type == 12, "Expected VTK hexahedral cells (type 12)."
    connectivity_length = 9

    ec = vtk.cells
    nn = len(ec)
    ec = ec.reshape([nn // connectivity_length, connectivity_length])
    content += 'EBLOCK,19,SOLID,' + (fmt % (len(ec), len(ec))) + "\n"
    content += "(19i10)\n"

    line = FortranRecordWriter('(19i10)')
    for i, e in enumerate(ec):
        e = e[1:] + 1
        content += line.write([1, 1, 1, 1, 0, 0, 0, 0, 8, 0, i + 1] + list(e)) + '\n'

    content += '        -1\nFINISH\n'

    with open(output_name + '_geom.cdb', 'w') as f:
        f.write(content)


def build_grain_dict(vtk):
    if GrainKey not in vtk.array_names:
        raise KeyError(f"'{GrainKey}' not found in VTK cell data.")
    if EulerAngleKey not in vtk.array_names:
        raise KeyError(f"'{EulerAngleKey}' not found in VTK cell data.")

    grain_dict = {}
    grain_ids = vtk[GrainKey]
    eulers = vtk[EulerAngleKey]

    for gid, ea in zip(grain_ids, eulers):
        gid = int(gid)
        if gid not in grain_dict:
            grain_dict[gid] = ea

    return grain_dict


def build_element_set_from_vtk(vtk):
    vtk = vtk.copy()
    vtk['ElementID'] = np.arange(vtk.n_cells) + 1
    vtk['CellIDs'] = np.arange(vtk.n_cells)

    element_set = {}
    unique_gids = np.unique(vtk[GrainKey]).astype(int)

    for gid in unique_gids:
        grain_elements = vtk.threshold([gid, gid], scalars=GrainKey)
        if 'ElementID' not in grain_elements.array_names:
            raise RuntimeError(f"Could not extract ElementID array for grain {gid}.")
        element_ids = np.asarray(grain_elements['ElementID'], dtype=int)

        if gid == 0:
            element_set[0] = element_ids
        else:
            element_set[gid] = element_ids

    return element_set


def write_named_selections(content, element_set, Eulers):
    empty_sets = []

    content += "/PREP7\n! Begin writing named selections\n\n"

    for curr_gid, grain_elems in sorted(element_set.items(), key=lambda x: int(x[0])):
        curr_gid = int(curr_gid)
        grain_elems = np.asarray(grain_elems, dtype=int)

        if len(grain_elems) < 1:
            empty_sets.append(curr_gid)
            continue

        content += f"CMBLOCK,GID{curr_gid},ELEM,{len(grain_elems):10d}\n"
        content += "(8i10)\n"

        for j, eid in enumerate(grain_elems):
            eid_str = str(int(eid))
            content += " " * (10 - len(eid_str)) + eid_str
            if (j + 1) % 8 == 0:
                content += "\n"

        if len(grain_elems) % 8 != 0:
            content += "\n"

    content += f"! Model contains {len(Eulers.keys())} grains\n"
    return content, set(empty_sets)


def write_elastic_block(content, matid, Eulers, E_, G_, v_):
    content += f"*SET,matid,{matid}\n"

    content += (
        "TB,ELAS,matid,,9,\n"
        f"TBDATA,1,{E_},{E_},{E_},{2 * G_},{2 * G_},{2 * G_}\n"
        f"TBDATA,7,{v_},{v_},{v_}\n"
    )

    content += f"TB,CTE,matid,\nTBDATA,1,{CTE},{CTE},{CTE}\n"

    my_ea = FormatEA(Eulers[matid])
    content += f"TB,XTAL,matid,,3,ORIE\nTBDATA,1,{my_ea[0]},{my_ea[1]},{my_ea[2]}\n"

    return content


def write_isotropic_hardening_block(content, matid, Eulers, E_, G_, v_):
    content += f"*SET,matid,{matid}\n"

    content += (
        "TB,ELAS,matid,,9,\n"
        f"TBDATA,1,{E_},{E_},{E_},{2 * G_},{2 * G_},{2 * G_}\n"
        f"TBDATA,7,{v_},{v_},{v_}\n"
    )

    content += f"TB,CTE,matid,\nTBDATA,1,{CTE},{CTE},{CTE}\n"

    my_ea = FormatEA(Eulers[matid])
    content += f"TB,XTAL,matid,,3,ORIE\nTBDATA,1,{my_ea[0]},{my_ea[1]},{my_ea[2]}\n"

    content += f"TB,BISO,matid,,2\nTBDATA,1,{YieldStress},{TangentModulus}\n"

    return content


def write_crystal_plasticity_block(content, matid, Eulers, E_, G_, v_):
    content += f"*SET,matid,{matid}\n"

    content += (
        "TB,ELAS,matid,,9,\n"
        f"TBDATA,1,{E_},{E_},{E_},{2 * G_},{2 * G_},{2 * G_}\n"
        f"TBDATA,7,{v_},{v_},{v_}\n"
    )

    content += f"TB,CTE,matid,\nTBDATA,1,{CTE},{CTE},{CTE}\n"

    content += "TB,PLAS,matid\n"

    my_ea = FormatEA(Eulers[matid])
    content += f"TB,XTAL,matid,,3,ORIE\nTBDATA,1,{my_ea[0]},{my_ea[1]},{my_ea[2]}\n"

    content += f"TB,XTAL,matid,,1,NSLFAM\nTBDATA,1,{nSF}\n"
    content += f"TB,XTAL,matid,,1,FORM\nTBDATA,1,{formulation}\n"

    content += f"TB,XTAL,matid,,{5 + nSF},XPARAM\nTBDATA,1,{CryType},0,{matid},{nSS},0"
    for sf in range(nSF):
        if sf + 6 == 7:
            content += "\nTBDATA,7"
        content += ",1"
    content += "\n"

    content += f"TB,XTAL,matid,1,{3 * (nSF + 1)},HARD\nTBTEMP,{T_ref},\nTBDATA,1"
    dat = (
        [ini_hardness] * nSF
        + [hardening_modulus] * nSF
        + [sat_hardness] * nSF
        + [r, n_, latent_hardening_ratio]
    )
    for i, val in enumerate(dat):
        if i % 6 == 0 and i > 0:
            mult = i // 6
            content += f"\nTBDATA,{6 * mult + 1}"
        content += f",{val}"
    content += "\n"

    content += f"TB,XTAL,matid,1,{len(flow_paras)},FL{CrystalType}\nTBTEMP,{T_ref},\nTBDATA,1"
    for fp in flow_paras:
        content += f",{fp}"
    content += "\n"

    return content


def WriteDAT(vtk_metadata, element_set, Eulers, output_name, Input_file_type):
    """
    vtk_metadata:
        Used only for optional geometry writing when Input_file_type == 'vtk'.
        Grain components and Euler-based material assignment are always written
        from element_set and Eulers.
    """
    content = ""

    # Optionally write geometry CDB if source is VTK
    if Input_file_type == 'vtk':
        vtk_geom = vtk_metadata.copy()
        vtk_geom.origin = np.zeros(3)
        vtk_geom = vtk_geom.scale([scale_factor, scale_factor, scale_factor], inplace=False)
        vtk2cdb(vtk_geom, output_name)

    # ALWAYS write grain components
    content, empty_sets = write_named_selections(content, element_set, Eulers)

    # Convert elastic properties
    if Elastic_type == 'CUBIC':
        if len(Elastic_constants) != 3:
            raise ValueError("Elastic_constants must contain [C11, C12, C44].")
        C11, C12, C44 = Elastic_constants
        E_ = (C11**2 + C12 * C11 - 2 * C12**2) / (C11 + C12)
        v_ = C12 / (C11 + C12)
        G_ = C44
    else:
        raise NotImplementedError("Please use the cubic elastic option.")

    content += "\n\n! Begin writing grain materials\n"

    for matid in sorted(Eulers.keys()):
        matid = int(matid)

        if matid in empty_sets:
            continue

        if matid == 0:
            content += "! Deactivate void\n"
            content += "CMSEL,S,GID0\n"
            content += "EKILL,ALL\n"
            content += "ALLSEL,ALL\n\n\n"
            continue

        if MaterialModel == 'elastic':
            content = write_elastic_block(content, matid, Eulers, E_, G_, v_)
        elif MaterialModel == 'isotropic_hardening':
            content = write_isotropic_hardening_block(content, matid, Eulers, E_, G_, v_)
        elif MaterialModel == 'crystal_plasticity':
            content = write_crystal_plasticity_block(content, matid, Eulers, E_, G_, v_)
        else:
            raise ValueError(
                "MaterialModel must be one of: "
                "'elastic', 'isotropic_hardening', 'crystal_plasticity'"
            )

        content += f"CMSEL,S,GID{matid}\n"
        content += "EMODIF,ALL,MAT,matid\n"
        content += "ALLSEL,ALL\n\n\n"

    content += f"ALLSEL,ALL\nTREF,{T_ref}\nTUNIF,{T_ref}\n/SOLU\n"

    out_dat = os.path.join(base_dir, f"{output_name}_{Input_file_type}_{MaterialModel}.dat")
    with open(out_dat, 'w') as f:
        f.write(content)

    print(f"Wrote: {out_dat}")


def main():
    print(f"Reading microstructure metadata from: {fn}.vtk")
    vtk = pv.read(os.path.join(base_dir, fn + '.vtk'))

    print(f"Cells in VTK: {vtk.n_cells}")
    if GrainKey not in vtk.array_names:
        raise KeyError(f"Missing grain ID array '{GrainKey}' in VTK.")
    if EulerAngleKey not in vtk.array_names:
        raise KeyError(f"Missing Euler angle array '{EulerAngleKey}' in VTK.")

    if np.max(vtk[EulerAngleKey]) <= 2.0 * np.pi:
        print("Euler angles in VTK appear to be in radians; FormatEA() will convert them.")

    grain_dict = build_grain_dict(vtk)
    element_set = build_element_set_from_vtk(vtk)

    print(f"Microstructure has {len(grain_dict.keys())} grains (including grain 0 if present).")
    print(f"Writing DAT for material model: {MaterialModel}")

    if Input_file_type == 'vtk':
        vtk_scaled = vtk.copy()
        vtk_scaled.origin = np.zeros(3)
        vtk_scaled = vtk_scaled.scale([scale_factor, scale_factor, scale_factor], inplace=False)
        print('After scaling, bounding box =',
              np.array(vtk_scaled.bounds)[1::2] - np.array(vtk_scaled.bounds)[0::2])

    WriteDAT(vtk, element_set, grain_dict, output_name, Input_file_type)


if __name__ == "__main__":
    main()