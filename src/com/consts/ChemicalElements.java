/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.consts;

import java.util.HashMap;
import java.util.Map;

public enum ChemicalElements {
	//radius 0.0 means no data! Just to avoid null pointer
	H(1, "Hydrogen", 1.008, 25.0, "1s1", "FFFFFF", "FFFFFF"),
	He(2, "Helium", 4.0026022, 120.0, "1s2", "D9FFFF", "FFC0CB"),
	Li(3, "Lithium", 6.94, 145.0, "[He],2s1", "CC80FF", "B22222"),
	Be(4, "Beryllium", 9.01218315, 105.0, "[He],2s2", "C2FF00", "FF1493"),
	B(5, "Boron", 10.81, 85.0, "[He],2s2,2p1", "FFB5B5", "00FF00"),
	C(6, "Carbon", 12.011, 70.0, "[He],2s2,2p2", "909090", "C8C8C8"),
	N(7, "Nitrogen", 14.007, 65.0, "[He],2s2,2p3", "3050F8", "8F8FFF"),
	O(8, "Oxygen", 15.999, 60.0, "[He],2s2,2p4", "FF0D0D", "F00000"),
	F(9, "Fluorine", 18.9984031636, 50.0, "[He],2s2,2p5", "90E050", "DAA520"),
	Ne(10, "Neon", 20.17976, 160.0, "[He],2s2,2p6", "B3E3F5", "FF1493"),
	Na(11, "Sodium", 22.989769282, 180.0, "[Ne],3s1", "AB5CF2", "0000FF"),
	Mg(12, "Magnesium", 24.305, 150.0, "[Ne],3s2", "8AFF00", "228B22"),
	Al(13, "Aluminium", 26.98153843, 125.0, "[Ne],3s2,3p1", "BFA6A6", "808090"),
	Si(14, "Silicon", 28.085, 110.0, "[Ne],3s2,3p2", "F0C8A0", "DAA520"),
	P(15, "Phosphorus", 30.9737619985, 100.0, "[Ne],3s2,3p3", "FF8000", "FFA500"),
	S(16, "Sulfur", 32.06, 100.0, "[Ne],3s2,3p4", "FFFF30", "FFC832"),
	Cl(17, "Chlorine", 35.45, 100.0, "[Ne],3s2,3p5", "1FF01F", "00FF00"),
	Ar(18, "Argon", 39.95, 71.0, "[Ne],3s2,3p6", "80D1E3", "FF1493"),
	K(19, "Potassium", 39.09831, 220.0, "[Ar],4s1", "8F40D4", "FF1493"),
	Ca(20, "Calcium", 40.0784, 180.0, "[Ar],4s2", "3DFF00", "808090"),
	Sc(21, "Scandium", 44.9559085, 160.0, "[Ar],3d1,4s2", "E6E6E6", "FF1493"),
	Ti(22, "Titanium", 47.8671, 140.0, "[Ar],3d2,4s2", "BFC2C7", "808090"),
	V(23, "Vanadium", 50.94151, 135.0, "[Ar],3d3,4s2", "A6A6AB", "FF1493"),
	Cr(24, "Chromium", 51.99616, 140.0, "[Ar],3d5,4s1", "8A99C7", "808090"),
	Mn(25, "Manganese", 54.9380432, 140.0, "[Ar],3d5,4s2", "9C7AC7", "808090"),
	Fe(26, "Iron", 55.8452, 140.0, "[Ar],3d6,4s2", "E06633", "FFA500"),
	Co(27, "Cobalt", 58.9331943, 135.0, "[Ar],3d7,4s2", "F090A0", "FF1493"),
	Ni(28, "Nickel", 58.69344, 135.0, "[Ar],3d8,4s2,or,[Ar],3d9,4s1(disputed,-,see,Nickel,article)", "50D050", "A52A2A"),
	Cu(29, "Copper", 63.5463, 135.0, "[Ar],3d10,4s1", "C88033", "A52A2A"),
	Zn(30, "Zinc", 65.382, 135.0, "[Ar],3d10,4s2", "7D80B0", "A52A2A"),
	Ga(31, "Gallium", 69.7231, 130.0, "[Ar],3d10,4s2,4p1", "C28F8F", "FF1493"),
	Ge(32, "Germanium", 72.6308, 125.0, "[Ar],3d10,4s2,4p2", "668F8F", "FF1493"),
	As(33, "Arsenic", 74.9215956, 115.0, "[Ar],3d10,4s2,4p3", "BD80E3", "FF1493"),
	Se(34, "Selenium", 78.9718, 115.0, "[Ar],3d10,4s2,4p4", "FFA100", "FF1493"),
	Br(35, "Bromine", 79.904, 115.0, "[Ar],3d10,4s2,4p5", "A62929", "A52A2A"),
	Kr(36, "Krypton", 83.7982, 0.0, "[Ar],3d10,4s2,4p6", "5CB8D1", "FF1493"),
	Rb(37, "Rubidium", 85.46783, 235.0, "[Kr],5s1", "702EB0", "FF1493"),
	Sr(38, "Strontium", 87.621, 200.0, "[Kr],5s2", "00FF00", "FF1493"),
	Y(39, "Yttrium", 88.905841, 180.0, "[Kr],4d1,5s2", "94FFFF", "FF1493"),
	Zr(40, "Zirconium", 91.2242, 155.0, "[Kr],4d2,5s2", "94E0E0", "FF1493"),
	Nb(41, "Niobium", 92.906371, 145.0, "[Kr],4d4,5s1", "73C2C9", "FF1493"),
	Mo(42, "Molybdenum", 95.951, 145.0, "[Kr],4d5,5s1", "54B5B5", "FF1493"),
	Tc(43, "Technetium", 98.0, 135.0, "[Kr],4d5,5s2", "3B9E9E", "FF1493"),
	Ru(44, "Ruthenium", 101.072, 130.0, "[Kr],4d7,5s1", "248F8F", "FF1493"),
	Rh(45, "Rhodium", 102.905492, 135.0, "[Kr],4d8,5s1", "0A7D8C", "FF1493"),
	Pd(46, "Palladium", 106.421, 140.0, "[Kr],4d10", "006985", "FF1493"),
	Ag(47, "Silver", 107.86822, 160.0, "[Kr],4d10,5s1", "C0C0C0", "808090"),
	Cd(48, "Cadmium", 112.4144, 155.0, "[Kr],4d10,5s2", "FFD98F", "FF1493"),
	In(49, "Indium", 114.8181, 155.0, "[Kr],4d10,5s2,5p1", "A67573", "FF1493"),
	Sn(50, "Tin", 118.7107, 145.0, "[Kr],4d10,5s2,5p2", "668080", "FF1493"),
	Sb(51, "Antimony", 121.7601, 145.0, "[Kr],4d10,5s2,5p3", "9E63B5", "FF1493"),
	Te(52, "Tellurium", 127.603, 140.0, "[Kr],4d10,5s2,5p4", "D47A00", "FF1493"),
	I(53, "Iodine", 126.904473, 140.0, "[Kr],4d10,5s2,5p5", "940094", "A020F0"),
	Xe(54, "Xenon", 131.2936, 0.0, "[Kr],4d10,5s2,5p6", "429EB0", "FF1493"),
	Cs(55, "Caesium", 132.905451966, 265.0, "[Xe],6s1", "57178F", "FF1493"),
	Ba(56, "Barium", 137.3277, 215.0, "[Xe],6s2", "00C900", "FFA500"),
	La(57, "Lanthanum", 138.905477, 195.0, "[Xe],5d1,6s2", "70D4FF", "FF1493"),
	Ce(58, "Cerium", 140.1161, 185.0, "[Xe],4f1,5d1,6s2", "FFFFC7", "FF1493"),
	Pr(59, "Praseodymium", 140.907661, 185.0, "[Xe],4f3,6s2", "D9FFC7", "FF1493"),
	Nd(60, "Neodymium", 144.2423, 185.0, "[Xe],4f4,6s2", "C7FFC7", "FF1493"),
	Pm(61, "Promethium", 145.0, 185.0, "[Xe],4f5,6s2", "A3FFC7", "FF1493"),
	Sm(62, "Samarium", 150.362, 185.0, "[Xe],4f6,6s2", "8FFFC7", "FF1493"),
	Eu(63, "Europium", 151.9641, 185.0, "[Xe],4f7,6s2", "61FFC7", "FF1493"),
	Gd(64, "Gadolinium", 157.253, 180.0, "[Xe],4f7,5d1,6s2", "45FFC7", "FF1493"),
	Tb(65, "Terbium", 158.9253548, 175.0, "[Xe],4f9,6s2", "30FFC7", "FF1493"),
	Dy(66, "Dysprosium", 162.5001, 175.0, "[Xe],4f10,6s2", "1FFFC7", "FF1493"),
	Ho(67, "Holmium", 164.9303287, 175.0, "[Xe],4f11,6s2", "00FF9C", "FF1493"),
	Er(68, "Erbium", 167.2593, 175.0, "[Xe],4f12,6s2", "00E675", "FF1493"),
	Tm(69, "Thulium", 168.9342186, 175.0, "[Xe],4f13,6s2", "00D452", "FF1493"),
	Yb(70, "Ytterbium", 173.04510, 175.0, "[Xe],4f14,6s2", "00BF38", "FF1493"),
	Lu(71, "Lutetium", 174.96681, 175.0, "[Xe],4f14,5d1,6s2", "00AB24", "FF1493"),
	Hf(72, "Hafnium", 178.492, 155.0, "[Xe],4f14,5d2,6s2", "4DC2FF", "FF1493"),
	Ta(73, "Tantalum", 180.947882, 145.0, "[Xe],4f14,5d3,6s2", "4DA6FF", "FF1493"),
	W(74, "Tungsten", 183.841, 135.0, "[Xe],4f14,5d4,6s2", "2194D6", "FF1493"),
	Re(75, "Rhenium", 186.2071, 135.0, "[Xe],4f14,5d5,6s2", "267DAB", "FF1493"),
	Os(76, "Osmium", 190.233, 130.0, "[Xe],4f14,5d6,6s2", "266696", "FF1493"),
	Ir(77, "Iridium", 192.2172, 135.0, "[Xe],4f14,5d7,6s2", "175487", "FF1493"),
	Pt(78, "Platinum", 195.0849, 135.0, "[Xe],4f14,5d9,6s1", "D0D0E0", "FF1493"),
	Au(79, "Gold", 196.9665704, 135.0, "[Xe],4f14,5d10,6s1", "FFD123", "DAA520"),
	Hg(80, "Mercury", 200.5923, 150.0, "[Xe],4f14,5d10,6s2", "B8B8D0", "FF1493"),
	Tl(81, "Thallium", 204.38, 190.0, "[Xe],4f14,5d10,6s2,6p1", "A6544D", "FF1493"),
	Pb(82, "Lead", 207.21, 180.0, "[Xe],4f14,5d10,6s2,6p2", "575961", "FF1493"),
	Bi(83, "Bismuth", 208.980401, 160.0, "[Xe],4f14,5d10,6s2,6p3", "9E4FB5", "FF1493"),
	Po(84, "Polonium", 209.0, 190.0, "[Xe],4f14,5d10,6s2,6p4", "AB5C00", "FF1493"),
	At(85, "Astatine", 210.0, 0.0, "[Xe],4f14,5d10,6s2,6p5", "754F45", "FF1493"),
	Rn(86, "Radon", 222.0, 0.0, "[Xe],4f14,5d10,6s2,6p6", "428296", "FF1493"),
	Fr(87, "Francium", 223.0, 0.0, "[Rn],7s1", "420066", "FF1493"),
	Ra(88, "Radium", 226.0, 215.0, "[Rn],7s2", "007D00", "FF1493"),
	Ac(89, "Actinium", 227.0, 195.0, "[Rn],6d1,7s2", "70ABFA", "FF1493"),
	Th(90, "Thorium", 232.03774, 180.0, "[Rn],6d2,7s2", "00BAFF", "FF1493"),
	Pa(91, "Protactinium", 231.035881, 180.0, "[Rn],5f2,6d1,7s2", "00A1FF", "FF1493"),
	U(92, "Uranium", 238.028913, 175.0, "[Rn],5f3,6d1,7s2", "008FFF", "FF1493"),
	Np(93, "Neptunium", 237.0, 175.0, "[Rn],5f4,6d1,7s2", "0080FF", "FF1493"),
	Pu(94, "Plutonium", 244.0, 175.0, "[Rn],5f6,7s2", "006BFF", "FF1493"),
	Am(95, "Americium", 243.0, 175.0, "[Rn],5f7,7s2", "545CF2", "FF1493"),
	Cm(96, "Curium", 247.0, 0.0, "[Rn],5f7,6d1,7s2", "785CE3", "FF1493"),
	Bk(97, "Berkelium", 247.0, 0.0, "[Rn],5f9,7s2", "8A4FE3", "FF1493"),
	Cf(98, "Californium", 251.0, 0.0, "[Rn],5f10,7s2", "A136D4", "FF1493"),
	Es(99, "Einsteinium", 252.0, 0.0, "[Rn],5f11,7s2", "B31FD4", "FF1493"),
	Fm(100, "Fermium", 257.0, 0.0, "[Rn],5f12,7s2", "B31FBA", "FF1493"),
	Md(101, "Mendelevium", 258.0, 0.0, "[Rn],5f13,7s2", "B30DA6", "FF1493"),
	No(102, "Nobelium", 259.0, 0.0, "[Rn],5f14,7s2", "BD0D87", "FF1493"),
	Lr(103, "Lawrencium", 266.0, 0.0, "[Rn],5f14,7s2,7p1", "C70066", "FF1493"),
	Rf(104, "Rutherfordium", 267.0, 0.0, "[Rn],5f14,6d2,7s2", "CC0059", "FF1493"),
	Db(105, "Dubnium", 268.0, 0.0, "[Rn],5f14,6d3,7s2", "D1004F", "FF1493"),
	Sg(106, "Seaborgium", 269.0, 0.0, "[Rn],5f14,6d4,7s2", "D90045", "FF1493"),
	Bh(107, "Bohrium", 270.0, 0.0, "[Rn],5f14,6d5,7s2", "E00038", "FF1493"),
	Hs(108, "Hassium", 270.0, 0.0, "[Rn],5f14,6d6,7s2", "E6002E", "FF1493"),
	Mt(109, "Meitnerium", 278.0, 0.0, "[Rn],5f14,6d7,7s2", "EB0026", "FF1493"),
	Ds(110, "Darmstadtium", 281.0, 0.0, "[Rn],5f14,6d8,7s2", "FF1493", "FF1493"),
	Rg(111, "Roentgenium", 282.0, 0.0, "[Rn],5f14,6d9,7s2", "FF1493", "FF1493"),
	Cn(112, "Copernicium", 285.0, 0.0, "[Rn],5f14,6d10,7s2", "FF1493", "FF1493"),
	Nh(113, "Nihonium", 286.0, 0.0, "[Rn],5f14,6d10,7s2,7p1", "FF1493", "FF1493"),
	Fl(114, "Flerovium", 289.0, 0.0, "[Rn],5f14,6d10,7s2,7p2", "FF1493", "FF1493"),
	Mc(115, "Moscovium", 290.0, 0.0, "[Rn],5f14,6d10,7s2,7p3", "FF1493", "FF1493"),
	Lv(116, "Livermorium", 293.0, 0.0, "[Rn],5f14,6d10,7s2,7p4", "FF1493", "FF1493"),
	Ts(117, "Tennessine", 294.0, 0.0, "[Rn],5f14,6d10,7s2,7p5", "FF1493", "FF1493"),
	Og(118, "Oganesson", 294.0, 0.0, "[Rn],5f14,6d10,7s2,7p6", "FF1493", "FF1493")
    ;

	private final int atomicNumber;
    private final String fullName;
    private final double atomicMass;
    private final double empricalRadius;
    private final String electConf;
    private final String colorJmol,
    colorRasmol;
    
    private ChemicalElements(int atomicNumber, String fullName, double atomicMass, double empricalRadius, String electConf, 
    		String colorJmol, String colorRasmol) {
        this.atomicNumber = atomicNumber;
        this.fullName = fullName;
        this.atomicMass = atomicMass;
        this.empricalRadius = empricalRadius;//unit:pm//radius 0.0 means no data! Just to avoid null pointer
        this.electConf = electConf;
        this.colorJmol = colorJmol;
        this.colorRasmol = colorRasmol;
        Holder.map.put(atomicNumber, this);
    }
    private static class Holder {
        static Map<Integer, ChemicalElements> map = new HashMap<Integer, ChemicalElements>();
    }
    public static ChemicalElements forAtomicNumber(int atomicNumber) {
        return Holder.map.get(atomicNumber);
    }

    public int getAtomicNumber() {
        return atomicNumber;
    }

    public String getFullName() {
        return fullName;
    }

    public double getAtomicMass() {
        return atomicMass;
    }
	public double getEmpricalRadius() {
		return empricalRadius;
	}
	public String getElectConf() {
		return electConf;
	}
	public String getColorJmol() {
		return colorJmol;
	}
	public String getColorRasmol() {
		return colorRasmol;
	}

}