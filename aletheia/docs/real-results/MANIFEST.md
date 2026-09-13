# 真实检测样本 / real detection samples

从本机已有的标准数据集中挑出，未做任何合成或美化。TIFF 源无损转为 PNG 以适配上传格式限制。
Curated from the standard datasets already on this machine — nothing synthesized.
TIFF sources are losslessly transcoded to PNG to fit the accepted upload formats.

| file | kind | size | bytes | ground truth | mask check | note | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| casia1_authentic_nat.jpg | authentic | 384x256 | 11 KiB | - | - | CASIA v1 authentic photo, no manipulation | CASIA1/Au/Au_nat_0001.jpg |
| casia1_authentic_ani.jpg | authentic | 384x256 | 16 KiB | - | - | CASIA v1 authentic photo, no manipulation | CASIA1/Au/Au_ani_0001.jpg |
| casia1_splice_plants.jpg | splicing | 384x256 | 62 KiB | casia1_splice_plants_gt.png | aligned | CASIA v1 splice, region pasted from another photo | CASIA1/Sp/Sp_D_CND_A_pla0005_pla0023_0281.jpg |
| casia1_copymove_nature.jpg | copy-move | 384x256 | 57 KiB | casia1_copymove_nature_gt.png | aligned | CASIA v1 copy-move, region duplicated inside the same photo | CASIA1/Sp/Sp_S_CNN_A_nat0078_nat0078_0004.jpg |
| casia2_splice_art.png | splicing | 384x256 | 133 KiB | casia2_splice_art_gt.png | aligned | CASIA v2 splice with post-processing, TIFF source | CASIA2/Tp/Tp_D_CND_M_N_art00076_art00077_10289.tif |
| columbia_splice_uncompressed.png | splicing | 757x568 | 513 KiB | - | - | Columbia uncompressed splice, two different cameras | columbia/4cam_splc/4cam_splc/canong3_canonxt_sub_01.tif |
| columbia_authentic_uncompressed.png | authentic | 757x568 | 467 KiB | - | - | Columbia uncompressed authentic capture | columbia/4cam_auth/4cam_auth/canong3_02_sub_01.tif |
| imd2020_realworld_01.jpg | real-world | 1920x1080 | 227 KiB | imd2020_realworld_01_gt.png | aligned | IMD2020 manipulation collected in the wild, 1920x1080 | IMD2020/1a07yi/c8swtoq_0.jpg |
| imd2020_realworld_01_original.jpg | authentic | 1200x1051 | 231 KiB | - | - | IMD2020 untouched original of the image above | IMD2020/1a07yi/1a07yi_orig.jpg |

`ground_truth/` 是数据集发布的标注掩码，供对照模型输出，不要作为上传输入。
`ground_truth/` holds the datasets' published masks, for comparison against
model output — they are not upload inputs.