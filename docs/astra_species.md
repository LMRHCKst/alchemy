# Вещества из базы АСТРА.4/pc

Разбор комплекта АСТРА.4/pc (МГТУ им. Н.Э. Баумана, автор Б.Г. Трусов,
руководство 1991 года, исполняемые файлы 1997 и 2004). Из всего комплекта
вытащен только список индивидуальных веществ: он текстовый и не зависит
от DOS. Остальное — бинарная база и скомпилированные программы.

Источник: `LIST_OF.SPE`, кодировка CP866.

## Что в списке

- записей: 2594, из них уникальных: **2517**
- разных формул без учёта фазы: **2080**
- газов и прочих: 1896
- конденсированных (пометка `(c)`): 698
- разных элементов: **80**
- заряженных частиц (ионы): 172
- органических соединений в газе: 171

Вещества повторяются, потому что в файле они сгруппированы по элементам:
кислород встречается и в блоке O, и в блоках соединений.

Самые частые элементы (по числу веществ):

| Элемент | Веществ |
|---|---|
| O | 769 |
| F | 530 |
| Cl | 461 |
| H | 394 |
| C | 269 |
| Br | 238 |
| I | 232 |
| S | 168 |
| N | 148 |
| B | 114 |
| Na | 109 |
| Li | 108 |

## Как устроена база

По руководству АСТРА, на каждое вещество в базе хранится: формула,
нижняя и верхняя границы температурной аппроксимации, семь
коэффициентов аппроксимации свободной энергии Гиббса и энтальпия
образования. Файл `ASTRA.BAS` — это и есть база, только в двоичном виде
(float32, 422 КБ), без имён внутри: порядок веществ жёстко зашит
в программу. Имя `.BAS` обманчиво, исходника там нет.

## Сверка с нашими справочниками

У нас 117 веществ. Из них в базе АСТРА есть
**103**. Сверка идёт по составу, а не по записи: АСТРА пишет
формулы по Хиллу (`C2H6O`), у нас часть записана структурно (`C2H5OH`),
и это одно и то же вещество.

Всего совпало по составу: **103**.
Есть у АСТРА, нет у нас: **1812** составов.

Наши вещества, которых у АСТРА нет совсем (14):

- `AgBr(тв)`
- `AgCl(тв)`
- `AgNO3(тв)`
- `Al(OH)3(тв)`
- `Al2(SO4)3(тв)`
- `C12H22O11(тв)`
- `C6H12O6(тв)`
- `CuSO4(тв)`
- `K2Cr2O7(тв)`
- `KMnO4(тв)`
- `NH4Cl(тв)`
- `NaHCO3(тв)`
- `PbSO4(тв)`
- `ZnSO4(тв)`

Совпавшие:

- `Ag(c)` — `Ag`
- `Ag2O(c)` — `Ag2O(тв)`
- `AgI(c)` — `AgI(тв)`
- `Al(c)` — `Al`
- `Al2O3(c)` — `Al2O3(тв)`
- `AlCl3(c)` — `AlCl3(тв)`
- `Ba(c)` — `Ba`
- `BaCO3(c)` — `BaCO3(тв)`
- `BaCl2(c)` — `BaCl2(тв)`
- `BaO(c)` — `BaO(тв)`
- `BaSO4(c)` — `BaSO4(тв)`
- `Br2` — `Br2`
- `C(c)` — `C(графит)`
- `C2H2` — `C2H2`
- `C2H4` — `C2H4`
- `C2H4O2` — `CH3COOH(ж)`
- `C2H6` — `C2H6`
- `C2H6O` — `C2H5OH(ж)`
- `C3H8` — `C3H8`
- `C4H10` — `C4H10`
- `C6H6` — `C6H6(ж)`
- `CH4` — `CH4`
- `CH4O` — `CH3OH(ж)`
- `CO` — `CO`
- `CO2` — `CO2`
- `CS2` — `CS2(ж)`
- `Ca(c)` — `Ca`
- `Ca2` — `Ca(OH)2(тв)`
- `CaCO3(c)` — `CaCO3(тв)`
- `CaCl2(c)` — `CaCl2(тв)`
- `CaO(c)` — `CaO(тв)`
- `CaSO4(c)` — `CaSO4(тв)`
- `Cl2` — `Cl2`
- `Cr(c)` — `Cr`
- `Cu(c)` — `Cu`
- `Cu2` — `Cu(OH)2(тв)`
- `Cu2O(c)` — `Cu2O(тв)`
- `CuO(c)` — `CuO(тв)`
- `F2` — `F2`
- `Fe(c)` — `Fe`
- `Fe2O3(c)` — `Fe2O3(тв)`
- `Fe3O4(c)` — `Fe3O4(тв)`
- `FeO(c)` — `FeO(тв)`
- `FeS(c)` — `FeS(тв)`
- `FeS2(c)` — `FeS2(тв)`
- `H2` — `H2`
- `H2O` — `H2O(г)`
- `H2O2(c)` — `H2O2(ж)`
- `H2S` — `H2S(г)`
- `H2SO4` — `H2SO4(ж)`
- `HBr` — `HBr(г)`
- `HCl` — `HCl(г)`
- `HF` — `HF(г)`
- `HI` — `HI(г)`
- `HNO3` — `HNO3(ж)`
- `Hg(c)` — `Hg`
- `I2` — `I2`
- `K(c)` — `K`
- `K2CO3(c)` — `K2CO3(тв)`
- `KBr(c)` — `KBr(тв)`
- `KCl(c)` — `KCl(тв)`
- `KI(c)` — `KI(тв)`
- `KNO3(c)` — `KNO3(тв)`
- `KOH(c)` — `KOH(тв)`
- `Mg(c)` — `Mg`
- `Mg2` — `Mg(OH)2(тв)`
- `MgCl2(c)` — `MgCl2(тв)`
- `MgO(c)` — `MgO(тв)`
- `MgSO4(c)` — `MgSO4(тв)`
- `Mn(c)` — `Mn`
- `MnO2(c)` — `MnO2(тв)`
- `N2` — `N2`
- `N2H4O3(c)` — `NH4NO3(тв)`
- `N2O` — `N2O`
- `N2O4` — `N2O4`
- `NH3` — `NH3(г)`
- `NO` — `NO`
- `NO2` — `NO2`
- `Na(c)` — `Na`
- `Na2CO3(c)` — `Na2CO3(тв)`
- `Na2O(c)` — `Na2O`
- `Na2O2(c)` — `Na2O2`
- `Na2SO4(c)` — `Na2SO4(тв)`
- `NaCl(c)` — `NaCl(тв)`
- `NaNO3(c)` — `NaNO3(тв)`
- `NaOH(c)` — `NaOH(тв)`
- `Ni(c)` — `Ni`
- `O2` — `O2`
- `P(c)` — `P(белый)`
- `Pb(c)` — `Pb`
- `PbO(c)` — `PbO(тв)`
- `PbO2(c)` — `PbO2(тв)`
- `PbS(c)` — `PbS(тв)`
- `S(c)` — `S(ромб)`
- `SO2` — `SO2`
- `SO3` — `SO3(г)`
- `Si(c)` — `Si`
- `SiO2(c)` — `SiO2(тв)`
- `Sn(c)` — `Sn`
- `Ti(c)` — `Ti`
- `Zn(c)` — `Zn`
- `ZnO(c)` — `ZnO(тв)`
- `ZnS(c)` — `ZnS(тв)`

Чего у нас нет (первые 60 по алфавиту):

- `Ag2S(c)`
- `AgO`
- `Al2`
- `Al2Br6`
- `Al2C2`
- `Al2Cl6`
- `Al2F6`
- `Al2I6`
- `Al2O`
- `Al2O2`
- `Al2S`
- `Al2S2`
- `Al2S3(c)`
- `Al4C3(c)`
- `AlBO2`
- `AlBr`
- `AlBr2`
- `AlBr3(c)`
- `AlC`
- `AlC2`
- `AlCl`
- `AlCl2`
- `AlClO(c)`
- `AlF`
- `AlF2`
- `AlF2Cl`
- `AlF3(c)`
- `AlF4-`
- `AlFCl`
- `AlFCl2`
- `AlH`
- `AlH2`
- `AlH2Cl`
- `AlH2F`
- `AlH3(c)`
- `AlHCl`
- `AlHCl2`
- `AlHF`
- `AlHF2`
- `AlHFCl`
- `AlI`
- `AlI2`
- `AlI3(c)`
- `AlN(c)`
- `AlO-`
- `AlO2`
- `AlO2H2`
- `AlO2H2Cl`
- `AlO2H2F`
- `AlO3H3(c)`
- `AlOCl2`
- `AlOF`
- `AlOF2`
- `AlOH`
- `AlOHCl`
- `AlOHCl2`
- `AlOHF`
- `AlOHF2`
- `AlS`
- `AlS2`

Остальное — в полном списке ниже.

## Что из этого следует

База АСТРА собрана под высокотемпературные задачи: горение, плазма,
ракетные топлива. Отсюда 172 иона, фториды и хлориды почти всех
элементов, оксиды тугоплавких металлов и верхняя граница 20000 К.

Школьной химии в ней меньше, чем ожидаешь: нет нитрата серебра,
хлорида серебра, сульфата меди, перманганата, дихромата, сахаров.
Это не пробел, а другое назначение базы.

Для нас отсюда полезен только перечень как контрольный список: если
когда-нибудь расширять свои справочники, видно, какие вещества бывают
в расчётных базах и в какой форме их записывают. Числа брать негде —
коэффициенты лежат в двоичном файле без имён.

## Полный список

Пометка `(c)` означает конденсированную фазу в базе АСТРА.

```
O               Xe              Se2             FNO2            As4
Sb2Se3(c)       C3H4            O2              Xe2             Se3
FNO3            AsO             SbTe            C3H6            H
XeO3            Se4             F3NO            AsO2            Sb2Te3(c)
C3H8            H2              XeO4            Se5             NHF
As2O3(c)        SbN             C4H             OH              XeF
Se6             NH2F            As2O5(c)        SbP             C4H2
HO2             XeF2(c)         Se7             NH4F(c)         As4O6
Bi(c)           C4H4            H2O             XeF2            Se8
NHF2            As4O7           Bi              C4H6            H2O2(c)
XeF4(c)         SeO             ClNO            As4O8           Bi2
C4H8            H2O2            XeF4            SeO2(c)         ClNO2
As4O9           Bi3             C4H10           F               XeF6(c)
SeO2            NS              As4O10          Bi4             C5H6
F2              XeF6            SeH             P(c)            AsH
BiO(c)          C5H8            FO              XeO2F2          H2Se
P               AsH3            BiO             C5H10           F2O
XeO3F2          SeS             P2              AsF             Bi2O3(c)
C5H12           HF              Pd2             Te(c)           P3
AsF3            Bi4O6           C6H6            H2F2            Rn
Te              P4              AsF5            BiH             C6H8
H3F3            S(c)            Te2             PO              AsS
BiH3            C6H10           H4F4            S               Te3
PO2             As2S3(c)        BiF             C6H12           H5F5
S2              Te4             P2O3            As4S4(c)        BiF3(c)
C6H14           H6F6            S3              Te5             P2O4
As4S4           BiF3            CHO             H7F7            S4
Te6             P2O5            AsSe            BiCl            CHO2
HOF             S5              Te7             P3O6            AsTe
BiCl3(c)        CH2O            Cl              S6              TeO
P4O6            AsN             BiCl3           CH2O2           Cl2
S7              TeO2(c)         P4O7            AsP             BiBr
CH3O            ClO             S8              TeO2            P4O8
Sb(c)           BiBr3(c)        CH4O            ClO2            SO
TeH             P4O9            Sb              BiBr3           C2H4O
Cl2O            SO2             H2Te            P4O10(c)        Sb2
BiI             C2H4O2          HCl             SO3             TeS
P4O10           Sb3             BiI3(c)         C2H6O           HOCl
S2O             TeSe            PH              Sb4             BiI3
C3H6O           ClF             SH              N               PH2
SbO             BiS             C4H8O           ClF3            H2S
N2              HPO             SbO2            Bi2S3(c)        CF
ClF5            HSO             N3              H3PO4(c)        Sb2O3(c)
BiSe            CF2             Br              SOH             NO
PF              Sb2O4(c)        Bi2Se3(c)       CF3             Br(c)
H2SO            NO2             PF2             Sb2O5(c)        BiTe
CF4             Br2             H2SO4           N2O             PF3
Sb4O6           Bi2Te3(c)       C2F             BrO             SF
N2O3            PF5             SbH             C(c)            C2F2
HBr             SF2             N2O4            POF3            SbH3
C               C2F3            BrF             SF3             N2O5
PCl             SbF             C2              C2F4            BrF3
SF4             NH              PCl2            SbF3(c)         C3
C2F5            BrF5            SF5             NH2             PCl3
SbF3            C4              C2F6            BrCl            SF6
NH3             PCl5            SbF5(c)         C5              FCO
I               S2F2            N2H2            POCl3           SbF5
CO              F2CO            I(c)            F2S2            N2H4
PFCl            SbCl            CO2             CHF             I2
S2F10           HN3             PF2Cl           SbCl3(c)        C2O
CH2F            IO              FSO             HNO             PF4Cl
SbCl3           C3O2            CH3F            HI              SOF2
HNO2            PFCl2           SbCl5(c)        CH              CHF2
IF              SO2F2           HNO3            PF3Cl2          SbCl5
CH2             CH2F2           IF5             SOF4            NH3O
PF2Cl3          SbBr            CH3             CHF3            IF7
HSO3F           N2H2O2          PFCl4           SbBr3(c)        CH4
C2HF            ICl             SOCl2           N2H4O3(c)       POF2Cl
SbBr3           C2H             C2H3F           IBr             SO2Cl2
NF              POFCl2          SbI             C2H2            C2H5F
He              HSO3Cl          NF2             PS              SbI3(c)
C2H3            C2H2F2          Ne              SF5Cl           NF3
PN              SbI3            C2H4            C2H4F2          Ar
SO2FCl          N2F2            As(c)           SbS             C2H5
C2HF3           Kr              Se(c)           N2F4            As2
Sb2S3(c)        C2H6            C2H3F3          KrF2            Se
FNO             As3             SbSe            C3H             C2H2F4
C2HF5           C2H4Br2         CS              SiC             SnCl4(c)
B               F2ClB3O3        AlCl2           HFCO            C2H3Br3
CS2             SiC2            SnCl4           B2              FCl2B3O3
AlCl3(c)        CCl             CF3Br           COS             Si2C
Sn2Cl4          BO              BHFCl           AlCl3           CCl2
CF2Br2          CN              Si2C2           SnBr            BO2
BBr             Al2Cl6          CCl3            CFBr3           N2C
Si3C            SnBr2           B2O             BBr2            AlClO(c)
CCl4            CH2FBr          CN2             Ge(c)           SnBr3
B2O2            BBr3            AlOCl           C2Cl            CHF2Br
C2N             Ge              SnBr4           B2O3(c)         BI
AlOCl2          C2Cl2           CHFBr2          C2N2            Ge2
SnI             B2O3            BI2             AlHCl           C2Cl3
CCl3Br          NCO             GeO             SnI2            BH
BI3             AlH2Cl          C2Cl4           CCl2Br2         HCN
GeO2(c)         SnI3            BH2             BS              AlHCl2
C2Cl5           CClBr3          HNC             GeO2            SnI4
BH3             BS2             AlOHCl          C2Cl6           CH2ClBr
C2HN            GeF             SnS(c)          B2H6            B2S
AlO2H2Cl        ClCO            CHCl2Br         C3HN            GeF2
SnS             HBO             B2S2            AlOHCl2         Cl2CO
CHClBr2         C5HN            GeF3            SnS2(c)         BOH
B2S3(c)         AlFCl           CHCl            CF2ClBr         C7HN
GeF4            SnS2            HBO2(c)         B2S3            AlF2Cl
CH2Cl           CFCl2Br         C9HN            GeCl            Pb(c)
HBO2            BN(c)           AlFCl2          CH3Cl           CFClBr2
FCN             GeCl2           Pb              BH2O            BN
AlHFCl          CHCl2           CI              ClCN            GeCl3
Pb2             BH2O2           BH6N            AlBr            CH2Cl2
CI2             CP              GeCl4           PbO(c)          BH3O
B3H6N3          AlBr2           CHCl3           CI3             Si(c)
GeBr            PbO             BH3O2           BC              AlBr3(c)
C2HCl           CI4             Si              GeBr2           PbO2(c)
H3BO3(c)        BC2             AlBr3           C2H3Cl          CH3I
Si2             GeBr3           PbO2            H3BO3           B2C
Al2Br6          C2H5Cl          CH2I2           Si3             GeBr4(c)
Pb2O2           B2H4O4          B4C(c)          AlI             C2H2Cl2
CHI3            SiO2(c)         GeBr4           Pb2O3(c)        H3B3O3
Al(c)           AlI2            C2H4Cl2         C2H5I           SiO2
GeI             Pb3O4(c)        H3B3O6          Al              AlI3(c)
C2HCl3          CF3I            SiH             GeI2(c)         PbH
BF              Al2             AlI3            C2H3Cl3         CF2I2
SiH2            GeI2            PbH4            BF2             AlO2
Al2I6           C2H2Cl4         CFI3            SiH3            GeI3
PbF             BF3             Al2O            AlS             HClCO
CH2FI           SiH4            GeI4(c)         PbF2(c)         B2F4
Al2O2           AlS2            CFCl            CHF2I           SiF
GeI4            PbF2            FBO             Al2O3(c)        Al2S
CF2Cl           CHFI2           SiF2            GeS(c)          PbF3
F2BO            Al2O3           Al2S2           CF3Cl           CCl3I
SiF3            GeS             PbF4(c)         B3F3O3(c)       AlH
Al2S3(c)        CFCl2           CCl2I2          SiF4            GeS2(c)
PbF4            F3B3O3          AlH2            AlN(c)          CF2Cl2
CClI3           SiHF            GeS2            Pb2F4           BHF
AlH3(c)         AlN             CFCl3           CH2ClI          SiCl
Sn(c)           PbCl            BH2F            AlH3            AlC
C2FCl           CHCl2I          SiCl2           Sn              PbCl2(c)
BHF2            AlOH            AlC2            C2F3Cl          CHClI2
SiCl3           Sn2             PbCl2           FBOH            HAlO
Al2C2           C2F2Cl2         CF2ClI          SiCl4           SnO(c)
PbCl3           FBO2H2          HAlO2           Al4C3(c)        C2FCl3
CFCl2I          SiHCl           SnO             PbCl4(c)        F2BOH
AlO2H2          AlBO2           FClCO           CFClI2          SiFCl
SnO2(c)         PbCl4           BCl             AlO3H3(c)       Ga(c)
CHFCl           CBr3I           SiBr            SnO2            Pb2Cl4
BCl2            AlO3H3          Ga              CH2FCl          CBr2I2
SiBr2           Sn2O2           PbBr            BCl3            AlF
GaO             CHF2Cl          CBrI3           SiBr3           SnH
PbBr2           B2Cl4           AlF2            Ga2O            CHFCl2
CH2BrI          SiBr4           SnH4            PbBr3           ClBO
AlF3(c)         Ga2O3(c)        C2H2FCl         CHBr2I          SiI
SnF             PbBr4           Cl2BO           AlF3            GaH
C2HF2Cl         CHBrI2          SiI2            SnF2(c)         PbI
Cl3B3O3         Al2F6           GaOH            C2HFCl2         CF2BrI
SiI3            SnF2            PbI2(c)         BHCl            AlOF
GaF             CBr             CFBr2I          SiI4            SnF3
PbI2            BH2Cl           AlOF2           GaF2            CBr2
CFBrI2          SiS(c)          SnF4(c)         PbI3            BHCl2
AlHF            GaF3(c)         CBr3            CHFBr           SiS
SnF4            PbI4            ClBOH           AlH2F           GaF3
CBr4            CCl2BrI         SiS2(c)         Sn2F4           PbS(c)
ClBO2H2         AlHF2           GaCl            CH3Br           CClBr2I
SiS2            SnCl            PbS             Cl2BOH          AlOHF
GaCl2           CH2Br2          CClBrI2         SiN             SnCl2(c)
PbS2            BFCl            AlO2H2F         GaCl3(c)        CHBr3
CHClBr          Si3N4(c)SnCl2   PbN2O6(c)       BF2Cl           AlOHF2
GaCl3           C2H5Br          CFClBr          SiC(c)          SnCl3
B(c)            BFCl2           AlCl            Ga2Cl6          In(c)
CdO(c)          Cu2             FeCl3(c)        NiI2(c)         MnS
CrO2Cl2         MoOF            In              CdO             CuO(c)
FeCl3           NiI2            MnS2(c)         CrOCl3          MoO2F
InO             CdH             CuO             Fe2Cl4          NiS(c)
Mn3N2(c)        CrOCl4          MoOF2           In2O            CdHO
Cu2O(c)         Fe2Cl6          NiS             Mn4N(c)         CrBr
MoO2F2(c)       In2O3(c)        CdO2H2(c)       CuH             FeOCl(c)
NiS2(c)         Mn5N2(c)        CrBr2(c)        MoO2F2          InH
CdO2H2          CuOH            FeOCl           Ni3S2(c)        Mn3C(c)
CrBr2           MoOF3           InOH            CdF             CuO2H2(c)
FeS(c)          NiB(c)          Mn7C3(c)        CrBr3(c)        MoOF4(c)
InF             CdF2(c)         CuF(c)          FeS             NiAl(c)
Cr(c)           CrBr3           MoOF4           InF2            CdF2
CuF             FeS2(c)         NiAl3(c)        Cr              CrBr4
MoCl            InF3(c)         Cd2F4           CuF2(c)         Fe2N(c)
Ni2Al3(c)       Cr2             CrI             MoCl2(c)        InF3
CdCl            CuF2            Fe4N(c)         Ni3Al(c)        CrO
CrI2(c)         MoCl2           InCl(c)         CdCl2(c)        Cu2F2
Fe3C(c)         Pd(c)           CrO2            CrI2            MoCl3(c)
InCl            CdCl2           Cu3F3           Fe2SiO4(c)      Pd
CrO3(c)         CrI3(c)         MoCl3           InCl2           Cd2Cl4
CuCl(c)         Co(c)           PdO(c)          CrO3            CrI3
MoCl4(c)        InCl3(c)        CdBr            CuCl            Co
PdO             Cr2O            CrI4            MoCl4           InCl3
CdBr2(c)        CuCl2(c)        CoO(c)          PdF2(c)         Cr2O2
CrS(c)          MoCl5(c)        In2Cl6          CdBr2           CuCl2
CoO             PdF2            Cr2O3(c)        CrS             MoCl5
Tl(c)           Cd2Br4          Cu2Cl2          Co3O4(c)        PdF4
Cr2O3           CrS2            MoCl6           Tl              CdI
Cu3Cl3          CoH             PdF6            CrH             Cr2S3(c)
MoOCl           TlO             CdI2(c)         Cu4Cl4          CoO2H2(c)
PdCl2(c)        CrOH            CrN(c)          MoO2Cl          Tl2O(c)
CdI2            Cu5Cl5          CoO2H2          PdCl2           CrO2H
CrN             MoOCl2(c)       Tl2O            Cd2I4           CuS(c)
CoF             Mn(c)           CrO3H           Cr2N(c)         MoOCl2
Tl2O3(c)        CdS(c)          CuS             CoF2(c)         Mn
CrO2H2          CrC2            MoO2Cl2(c)      TlH             CdS
Cu2S(c)         CoF2            MnO(c)          CrO3H2          Cr3C2(c)
MoO2Cl2         TlOH            CdSO4(c)        Cu2S            CoF3(c)
MnO             CrO4H2          Cr7C3(c)        MoOCl3(c)       TlF(c)
CdSe(c)         Ag(c)           CoF3            MnO2(c)         CrO3H3
C6Cr23(c)       MoOCl3          TlF             CdTe(c)         Ag
CoCl            MnO2            CrO4H3          CrSi(c)         MoOCl4(c)
Tl2F2           Hg(c)           AgO             CoCl2(c)        Mn2O3(c)
CrO4H4          CrSi2(c)        MoOCl4          TlCl(c)         Hg
Ag2O(c)         CoCl2           Mn2O7(c)        CrO5H4          Cr3Si(c)
MoBr            TlCl            Hg2             AgI(c)          Co2Cl4
Mn3O4(c)        CrF             Cr5Si3(c)       MoBr2(c)        Tl2Cl2
HgO(c)          AgI             CoBr            MnH             CrF2(c)
Mo(c)           MoBr2           Zn(c)           HgO             Ag2S(c)
CoBr2(c)        MnOH            CrF2            Mo              MoBr3(c)
Zn              HgH             Fe(c)           CoBr2           MnO2H(c)
CrF3(c)         MoO             MoBr3           ZnO(c)          HgF
Fe              CoI             MnO2H2(c)       CrF3            MoO2(c)
MoBr4(c)        ZnO             HgF2(c)         FeO(c)          CoI2(c)
MnF             CrF4            MoO2            MoBr4           Zn2O
HgF2            FeO             CoI2            MnF2(c)         CrF5
MoO3(c)         MoBr5           ZnH             Hg2F2(c)        FeO2
Ni(c)           MnF2            CrF6            MoO3            MoBr6
ZnO2H2(c)HgCl   Fe2O3(c)        Ni              MnF3(c)         CrOF
Mo2O6           MoO2Br2         ZnF             HgCl2(c)        Fe3O4(c)
NiO(c)          MnF3            CrO2F           Mo3O9           MoI
ZnF2(c)         HgCl2           FeOH            NiO             MnF4(c)
CrOF2           Mo4O12          MoI2            ZnF2            Hg2Cl2(c)
FeO2H           NiH             MnF4            CrO2F2          Mo5O15
ZnCl            HgBr            NiOH            MnF5            CrOF3
MoOH            MoI3(c)         ZnCl2(c)        HgBr2(c)        FeO2H2(c)
NiO2H(c)        MnF6            CrOF4(c)        MoO2H           MoI3
ZnCl2           HgBr2           FeO2H2          NiO2H2(c)       MnO3F
CrOF4           MoO2H2          MoI4(c)         ZnBr            Hg2Br2(c)
FeO3H3(c)       NiO2H2          MnCl            CrCl            MoO3H2
MoI4            ZnBr2(c)        HgI             FeF             NiF
MnCl2(c)        CrCl2(c)        MoO4H2          MoI5            ZnBr2
HgI2(c)         FeF2(c)         NiF2(c)         MnCl2           CrCl2
MoF             MoI6            ZnI             HgI2            FeF2
NiF2            MnCl3(c)        CrCl3(c)        MoF2            MoS
ZnI2(c)         Hg2I2(c)        FeF3(c)         NiCl            MnCl3
CrCl3           MoF3(c)         MoS2(c)         ZnI2            HgS(c)
FeF3            NiCl2(c)        MnCl4           CrCl4           MoF3
MoS2            ZnS(c)          HgS             Fe2F4           NiCl2
MnCl5           CrCl5           MoF4            MoN             ZnS
HgSe(c)         Fe2F6           NiBr            MnCl6           CrCl6
MoF5(c)         Mo2N(c)         Cd(c)           HgTe(c)         FeCl
NiBr2(c)        Mn2Cl4          CrOCl           MoF5            Mo2C(c)
Cd              Cu(c)           FeCl2(c)        NiBr2           MnO3Cl
CrO2Cl          MoF6(c)         Mo3C2(c)        Cd2             Cu
FeCl2           NiI             MnS(c)          CrOCl2          MoF6
MoSi2(c)        W(c)            WBr2            VS              TaF3
TiBr2           ZrBr4           Y2O2            Sm2O3(c)        W
WBr3            VN(c)           TaF4            TiBr3(c)        ZrI
Y2O3(c)         Eu(c)           WO              WBr4(c)         VN
TaF5(c)         TiBr3           ZrI2(c)         La(c)           Eu
WO2(c)          WBr4            VC(c)           TaF5            TiBr4(c)
ZrI2            La              EuO(c)          WO2             WBr5(c)
VC2             TaOF3           TiBr4           ZrI3(c)         La2
EuO             WO3(c)          WBr5            VC4             TaCl
TiI(c)          ZrI3            LaO             Eu2O3(c)        WO3
WBr6(c)         VSi2(c)         TaCl2(c)        TiI             ZrI4(c)
LaO2            Gd(c)           W2O6            WBr6            V3Si(c)
TaCl2           TiI2(c)         ZrI4            La2O            Gd
W3O8            WO2Br2          V5Si3(c)        TaCl3(c)        TiI2
ZrS             La2O2           GdO             W3O9            WI
VB(c)           TaCl3           TiI3(c)         ZrS2(c)         La2O3(c)
Gd2O3(c)        W4O12           WI2             VB2(c)          TaCl4(c)
TiI3            ZrS2            LaH2(c)         Tb(c)           W5O15
WI3             V3B4(c)         TaCl4           TiI4(c)         ZrN(c)
LaF             Tb              WOH             WI4             V5B6(c)
TaCl5(c)        TiI4            ZrN             LaF3(c)         TbO
WO2H            WI5             Nb(c)           TaCl5           TiS(c)
ZrC(c)          LaF3            Tb2O3(c)        WO2H2           WI6
Nb              TaOCl3          TiS             ZrSi(c)         LaCl
TbH2(c)         WO3H2           WS              NbO(c)          TaBr5
TiS2(c)         ZrSi2(c)        LaCl3(c)        Dy(c)           WO4H2
WS2(c)          NbO             TaOBr3          TiS2            ZrB2(c)
LaCl3           DyO             WF              WS2             NbO2(c)
TaI5            TiN(c)          Zr2Al(c)        LaS(c)          Dy2O3(c)
WF2             W2N(c)          NbO2            TaOI3           TiN
Zr4Al3(c)       La2S3(c)        DyH2(c)         WF3             WC(c)
Nb2O5(c)        TaN(c)          TiC(c)          ZrAl2(c)        LaN(c)
Ho(c)           WF4(c)          W2C(c)          NbH(c)          TaN
TiSi(c)         ZrAl3(c)        LaB6(c)         HoO             WF4
V(c)            NbF             Ta2N(c)         TiSi2(c)        Hf(c)
Ce(c)           Ho2O3(c)        WF5(c)          V               NbF2
TaC(c)          Ti5Si3(c)       Hf              Ce              HoH2(c)
WF5             VO(c)           NbF3            Ti(c)           TiB(c)
HfO             Ce2             Er(c)           WF6             VO
NbF4            Ti              TiB             HfO2(c)         CeO
Er              WOF             VO2             NbF5(c)         TiO(c)
TiB2(c)         HfO2            CeO2(c)         ErO             WO2F
V2O3(c)         NbF5            TiO             Zr(c)           HfF
Ce2O3(c)        Er2O3(c)        WOF2            V2O4(c)         NbOF3
TiO2(c)         Zr              HfF2(c)         CeH2(c)         Tm(c)
WO2F2           V2O5(c)         NbCl            TiO2            Zr2
HfF2            CeF             TmO             WOF3            V4O8
NbCl2           Ti2O3(c)        ZrO             HfF3(c)         CeF3(c)
Tm2O3(c)        WOF4(c)         V4O10           NbCl3           Ti3O5(c)
ZrO2(c)         HfF3            CeF3            Yb(c)           WOF4
VH(c)           NbCl4           Ti4O7(c)        ZrO2            HfF4(c)
CeF4(c)         Yb              WCl             VF              NbCl5(c)
TiH2(c)         ZrH             HfF4            CeCl            YbO
WCl2(c)         VF2(c)          NbCl5           TiOH            ZrH2(c)
HfCl            CeCl3(c)        Yb2O3(c)        WCl2            VF2
NbOCl3          TiF             ZrOH            HfCl2(c)        CeCl3
Lu(c)           WCl3(c)         VF3(c)          NbBr5           TiF2(c)
ZrF             HfCl2           CeS(c)          Th(c)           WCl3
VF3             NbOBr3          TiF2            ZrF2(c)         HfCl3(c)
Ce2S3(c)        Th              WCl4(c)         VF4(c)          NbI5
TiF3(c)         ZrF2            HfCl3           CeN(c)          ThO
WCl4            VF4             NbOI3           TiF3            ZrF3(c)
HfCl4(c)        Pr(c)           ThO2(c)         WCl5(c)         VF5(c)
NbN(c)          TiF4(c)         ZrF3            HfCl4           Pr
ThO2            WCl5            VF5             NbN             TiF4
ZrF4(c)         HfN(c)          PrO             ThF             WF6(c)
VOF3            Nb2N(c)         TiOF            ZrF4            HfN
Pr2O3(c)        ThF2            WCl6            VCl             NbC(c)
TiOF2           ZrCl            HfC(c)          PrH2(c)         ThF3(c)
VCl2(c)         Nb2C(c)         TiCl            ZrCl2(c)        Sc(c)
Nd(c)           ThF3            WOCl            VCl2            NbSi2(c)
TiCl2(c)        ZrCl2           Sc              Nd              ThF4(c)
WO2Cl           VCl3(c)         Ta(c)           TiCl2           ZrCl3(c)
ScO             NdO             ThF4            WOCl2(c)        VCl3
Ta              TiCl3(c)        ZrCl3           ScO2            Nd2O3(c)
ThCl            WOCl2           VCl4(c)         TaO             TiCl3
ZrCl4(c)        Sc2O            NdH2(c)         ThCl2           WO2Cl2(c)
VCl4            TaO2            TiCl4(c)        ZrCl4           Sc2O2
Pm(c)           ThCl3(c)        WO2Cl2          VCl5            Ta2O5(c)
TiCl4           ZrBr            Sc2O3(c)        Pm              ThCl3
WOCl3(c)        VOCl3           Ta2H(c)         TiOCl           ZrBr2(c)
Y(c)            PmO             ThCl4(c)        WOCl3           VBr5
TaF             TiOCl2          ZrBr2           Y               Pm2O3(c)
ThCl4           WOCl4(c)        VOBr3           TaF2(c)         TiBr(c)
ZrBr3(c)        YO              Sm(c)           U(c)            WOCl4
VI5             TaF2            TiBr            ZrBr3           YO2
Sm              U               WBr             VOI3            TaF3(c)
TiBr2(c)        ZrBr4(c)        Y2O             SmO             UO
UO2(c)          BeOHF           Mg3N2(c)        CaC2(c)         BaH
LiCl(c)         NaF(c)          UO2             BeCl            MgN2O6(c)
CaCO3(c)        BaH2(c)         LiCl            NaF             UO3(c)
BeCl2(c)        MgP2O6(c)       CaSiO3(c)       BaOH            Li2Cl2
Na2F2           UO3             BeCl2           Mg2P2O7(c)      Ca2SiO4(c)
BaO2H2(c)       Li3Cl3          Na3F3           U3O8(c)         Be2Cl4
Mg3P2O8(c)      Ca3Si2O7(c)     BaO2H2          LiOCl           NaCl(c)
U4O9(c)         BeOHCl          MgC2(c)         CaTiO3(c)       BaF
LiClO4(c)       NaCl            UF              BeBr            Mg2C3(c)
Ca3Ti2O7(c)     BaF2(c)         Li2FCl          Na2Cl2          UF2
BeBr2(c)        MgCO3(c)        CaZrO3(c)       BaF2            LiBr(c)
Na3Cl3          UF3(c)          BeBr2           Mg2Si(c)        Sr(c)
BaOHF           LiBr            NaClO3(c)       UF3             BeOHBr
MgSiO3(c)       Sr              BaCl            Li2Br2          NaClO4(c)
UF4(c)          BeI             Mg2SiO4(c)      Sr2             BaCl2(c)
Li3Br3          Na2FCl          UF4             BeI2(c)         MgB2(c)
SrO(c)          BaCl2           Li2FBr          NaBr(c)         UF5(c)
BeI2            MgB4(c)         SrO             BaOHCl          Li2ClBr
NaBr            UF5             BeOHI           MgB12(c)        SrH
BaBr            LiI(c)          Na2Br2          UF6(c)          BeS(c)
MgBO2           SrH2(c)         BaBr2(c)        LiI             Na2FBr
UF6             BeS             MgB2O4          SrOH            BaBr2
Li2I2           Na2ClBr         UOF             BeSO4(c)        MgAl2O4(c)
SrO2H2(c)       BaOHBr          Li3I3           NaI(c)          UO2F
BeN             MgTiO3(c)       SrO2H2          BaI             Li2FI
NaI             UOF2            Be3N2(c)        MgTi2O5(c)      SrF
BaI2(c)         Li2ClI          Na2I2           UO2F2(c)        BeC2
Mg2TiO4(c)      SrF2(c)         BaI2            Li2BrI          Na2FI
UO2F2           Be2C(c)         Ca(c)           SrF2            BaOHI
LiS             Na2ClI          UOF3            BeCO3(c)        Ca
SrOHF           BaS(c)          Li2S(c)         Na2BrI          UOF4
Be2SiO4(c)      Ca2             SrCl            BaS             Li2SO4(c)
NaS             UCl             BeBO2           CaO(c)          SrCl2(c)
BaSO4(c)        LiN             Na2S(c)         UCl2            BeB2O4
CaO             SrCl2           Ba3N2(c)        Li3N(c)         Na2SO4(c)
UCl3            Mg(c)           CaH             SrOHCl          BaN2O4(c)
LiON            Na2SO4          UCl4            Mg              CaH2(c)
SrBr            BaN2O6(c)       LiNO2(c)        NaN             UCl5
Mg2             CaOH            SrBr2(c)        BaP2O6(c)       LiNO2
NaON            Pu(c)           MgO(c)          CaO2H2(c)       SrBr2
Ba2P2O7(c)      LiNO3(c)        NaNO2(c)        Pu              MgO
CaO2H2          SrOHBr          Ba3P2O8(c)      LiNO3           NaNO2
PuO             MgH             CaF             SrI             BaCO3(c)
LiPO3(c)        NaNO3(c)        PuO2(c)         MgH2(c)         CaF2(c)
SrI2(c)         BaSiO3(c)       LiPO3           NaNO3           PuO2
MgOH            CaF2            SrI2            BaAl2O4(c)      Li2C2(c)
NaOP            Pu2O3(c)        MgO2H2(c)       CaOHF           SrOHI
BaCr2O4(c)      Li2CO3(c)       NaPO2           Be(c)           MgO2H2
CaCl            SrS(c)          BaTiO3(c)       Li2SiO3(c)      NaPO3(c)
Be              MgF             CaCl2(c)        SrS             Ba2TiO4(c)
Li2Si2O5(c)     NaPO3           Be2             MgF2(c)         CaCl2
SrSO4(c)        BaZrO3(c)       LiB10(c)        Na2C2(c)        BeO(c)
MgF2            CaOHCl          Sr3N2(c)        Li(c)           LiBO2(c)
Na2CO3(c)       BeO             MgOHF           CaBr            SrN2O4(c)
Li              LiBO2           Na2SiO3(c)      Be2O            MgCl
CaBr2(c)        SrN2O6(c)       Li2             LiAlF4          Na2Si2O5(c)
Be2O2           MgCl2(c)        CaBr2           SrP2O6(c)       LiO
Li3AlF6(c)      NaBO2(c)        Be3O3           MgCl2           CaOHBr
Sr2P2O7(c)      Li2O(c)         Na(c)           NaBO2           Be4O4
MgOHCl          CaI             Sr3P2O8(c)      Li2O            Na
NaAlO2(c)       Be5O5           MgBr            CaI2(c)         SrCO3(c)
Li2O2(c)        Na2             NaAlF4          Be6O6           MgBr2(c)
CaI2            SrSiO3(c)       Li2O2           NaO             Na3AlF6(c)
BeH             MgBr2           CaOHI           SrAl2O4(c)      LiH(c)
NaO2(c)         Na5Al3F14(c)    BeH2            MgOHBr          CaS(c)
SrCr2O4(c)      LiH             Na2O(c)         NaFeO2(c)       BeOH
MgI             CaS             SrTiO3(c)       LiOH(c)         Na2O
Na4FeO3(c)      BeO2H2(c)       MgI2(c)         CaSO4(c)        Sr2TiO4(c)
LiOH            Na2O2(c)        LiNa            BeO2H2          MgI2
Ca3N2(c)        SrZrO3(c)       Li2O2H2         Na2O2           LiNaF2
BeF             MgOHI           CaN2O4(c)       Ba(c)           LiF(c)
NaH(c)          LiNaCl2         BeF2(c)         MgS(c)          CaN2O6(c)
Ba              LiF             NaH             LiNaFCl         BeF2
MgS             CaP2O6(c)       Ba2             Li2F2           NaOH(c)
LiNaBr2         Be2F4           MgSO4(c)        Ca2P2O7(c)      BaO(c)
Li3F3           NaOH            LiNaFBr         Be2OF2          MgN
Ca3P2O8(c)      BaO             LiOF            Na2O2H2         LiNaClBr
LiNaI2          KBO2            RbI             Cs2             LiCsFI
Ne+             AlO-            UF+             LiNaFI          KAlO2(c)
Rb2I2           CsO             LiCsClI         Ar+             AlO2-
UF-             LiNaClI         KAlF4           Rb2FI           CsO2(c)
LiCsBrI         Kr+             AlF2-           UF2+            LiNaBrI
K3AlF6(c)       Rb2ClI          Cs2O(c)         NaCs            Xe+
AlF4-           UF2-            K(c)            KUF5            Rb2BrI
Cs2O            NaCsF2          Rn+             Ga+             UF3+
K               LiK             RbS             Cs2O2(c)        NaCsCl2
S-              In+             UF3-            KO              LiKF2
Rb2S(c)         Cs2O2           NaCsFCl         S2-             Tl+
UF4+            KO2(c)          LiKCl2          RbSO4(c)        CsH(c)
NaCsBr2         S3-             Zn+             UF4-            K2O(c)
LiKFCl          RbSO4           CsH             NaCsFBr         SO-
Cd+             UF5+            K2O             LiKBr2          RbN
CsOH(c)         NaCsClBr        SO2-            Hg+             UF5-
K2O2(c)         LiKFBr          RbON            CsOH            NaCsI2
SH-             Cu+             UF6-            K2O2            LiKClBr
RbNO2(c)        Cs2O2H2         NaCsFI          SF-             Fe+
Pu+             KH(c)           LiKI2           RbNO2           CsF(c)
NaCsClI         SF3-            Co+             PuO+            KH
LiKFI           RbNO3(c)        CsF             NaCsBrI         SF5-
Ni+             PuO2+           KOH(c)          LiKClI          RbNO3
Cs2F2           KCs             SF6-            Mn+             PuO2-
KOH             LiKBrI          RbPO3(c)        CsCl(c)         KCsF2
Se-             Cr+             Be+             K2O2H2          NaK
RbPO3           CsCl            KCsCl2          Te-             CrO3-
Mg+             KF(c)           NaKF2           Rb2CO3(c)       Cl2Cs2
KCsFCl          N+              Mo+             Ca+             KF
NaKCl2          RbBO2(c)        CsClO4(c)       KCsBr2          N2+
MoO3-           CaO+            K2F2            NaKFCl          RbBO2
Cs2FCl          KCsFBr          NO+             W+              CaOH+
KCl(c)          NaKBr2          LiRb            CsBr(c)         KCsClBr
NO2+            WO3-            CaF+            KCl             NaKFBr
LiRbF2          CsBr            KCsI2           NO2-            V+
CaCl+           K2Cl2           NaKClBr         LiRbCl2         Cs2Br2
KCsFI           NO3-            Nb+             Sr+             KClO3(c)
NaKI2           LiRbFCl         Cs2FBr          KCsClI          N2O+
Ta+             SrO+            KClO4(c)        NaKFI           LiRbBr2
Cs2ClBr         KCsBrI          NH+             Ti+             SrOH+
K2FCl           NaKClI          LiRbFBr         CsI(c)          RbCs
NH4+            TiO+            SrF+            KBr(c)          NaKBrI
LiRbClBr        CsI             RbCsF2          PO-             Zr+
SrCl+           KBr             Rb(c)           LiRbI2          Cs2I2
RbCsCl2         PO2-            ZrO+            BaO+            K2Br2
Rb              LiRbFI          Cs2FI           RbCsFCl         PH2-
Hf+             BaOH+           K2FBr           Rb2             LiRbClI
Cs2ClI          RbCsBr2         PF2-            HfO+            BaF+
K2ClBr          RbO             LiRbBrI         Cs2BrI          RbCsFBr
PCl2-           Sc+             BaCl+           KI(c)           RbO2(c)
NaRb            CsS             RbCsClBr        PFCl-           ScO+
Li+             KI              Rb2O(c)         NaRbF2          Cs2S(c)
RbCsI2          As+             Y+              Li2+            K2I2
Rb2O            NaRbCl2         Cs2SO4(c)       RbCsFI          Sb-
YO+             Li3+            K2FI            Rb2O2(c)        NaRbFCl
Cs2SO4          RbCsClI         SbO2-           La+             Li2O+
K2ClI           Rb2O2           NaRbBr2         CsN             RbCsBrI
C+              LaO+            Na+             K2BrI           RbH(c)
NaRbFBr         CsON            O+              C-              Ce+
Na2O+           KS              RbH             NaRbClBr        CsNO2(c)
O-              C2+             Pr+             K+              K2S(c)
RbOH(c)         NaRbI2          CsNO2           O2+             C2-
Pm+             K2+             K2SO4(c)        RbOH            NaRbFI
CsNO3(c)        O2-             CO+             Sm+             K2O+
K2SO4           Rb2O2H2         NaRbClI         CsNO3           H+
CO2+            Eu+             Rb+             KN              RbF(c)
NaRbBrI         CsPO3(c)        H-              CH+             Gd+
Cs+             KON             RbF             KRb             CsPO3
H2+             CHO+            Tb+             Cs2O+           KNO2(c)
Rb2F2           KRbF2           Cs2CO3(c)       H3+             CN+
Dy+             End             KNO2            RbCl(c)         KRbCl2
Cs2CO3          OH+             CN-             Ho+             KNO3(c)
RbCl            KRbFCl          CsBO2(c)        OH-             Si+
Tm+             KNO3            Rb2Cl2          KRbBr2          CsBO2
HO2-            Ge+             Yb+             KPO3(c)         RbClO4(c)
KRbFBr          LiCs            H2O+            Sn+             ThO+
KPO3            Rb2FCl          KRbClBr         LiCsF2          H3O+
Pb+             ThO2+           K2CO3(c)        RbBr(c)         KRbI2
LiCsCl2         F-              B+              ThO2-           K2CO3
RbBr            KRbFI           LiCsFCl         F2H-            BO-
U+              K2SiO3(c)       Rb2Br2          KRbClI          LiCsBr2
Cl-             BO2-            UO+             K2Si2O5(c)Rb2FBr  KRbBrI
LiCsFBr         Br-             BF2-            UO2+            K2Si4O9(c)Rb2ClBr
Cs(c)           LiCsClBr        I-              BF4-            UO2-
KBO2(c)         RbI(c)          Cs              LiCsI2          He+
Al+             UO3-            Dy              Ho              Tm
Lu              As
```

Сгенерировано `tools/extract_astra.py`.
