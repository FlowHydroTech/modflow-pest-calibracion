

rm -f \
  pp_reg_kx.dat \
  pp_reg_vani.dat \
  pp_reg_ss.dat \
  pp_reg_sy.dat \
  pp_loc_kx.dat \
  pp_loc_vani.dat \
  pp_loc_ss.dat \
  pp_loc_sy.dat

./ensimod cmdic_rajos_ensi


#!/usr/bin/env bash
rm -f \
  CMDIC_Rajos.hds \
  CMDIC_Rajos.cbcln \
  CMDIC_Rajos.cbb \
  CMDIC_Rajos.lst \
  CMDIC_Rajos_SS.lst \
  CMDIC_Rajos_SS.hds \
  CMDIC_Rajos_SS.cbb \
  drains_cln.smp \
  wells_cln.smp \
  caudalesDrenes.smp \
  caudalesGHB.smp \
  balance_all.2.csv \
  niveles_simulados_obs.mod2obs \
  niveles_simulados_scv.mod2obs \
  niveles_simulados_obs.smp \
  niveles_simulados_obs_ss.smp \
  niveles_simulados_scv.smp \
  smpdiff_obs.smp \
  smpdiff_scv.smp \
  gradientes_scv.smp\
  ghb_penalty.smp\
  ghb_penalty_violaciones.csv\
  drenes_rajos_penalty.smp\
  drenes_rajos_penalty_violaciones.csv

wine ./plproc.exe plproc_kx_main_usg.dat
wine ./plproc.exe plproc_vani_main_usg.dat
wine ./plproc.exe plproc_ss_main_usg.dat
wine ./plproc.exe plproc_sy_main_usg.dat

./mfusgt270 CMDIC_Rajos_SS.nam
./mfusgt270 CMDIC_Rajos_0.nam

wine ./usgbud2smp.exe < bud2smp_q_drains_cln.in
wine ./usgbud2smp.exe < bud2smp_q_wells_cln.in
wine ./usgbud2smp1.exe < usgbud2smp_Drenes.in
wine ./usgbud2smp1.exe < usgbud2smp_GHB.in
wine ./zonbudusg.exe < zonebud_all.in
wine ./usgmod2obs.exe < mod2obs_obs.in
wine ./usgmod2obs.exe < mod2obs_scv.in
wine ./usgmod2smp.exe < mod2smp_obs.in
wine ./usgmod2smp.exe < mod2smp_obs_ss.in
wine ./usgmod2smp.exe < mod2smp_scv.in
wine ./smpdiff.exe < smpdiff_obs.in
wine ./smpdiff.exe < smpdiff_scv.in

python3 gradientes.py
python3 ghb_penalty.py
python3 drenes_rajos_penalty.py

