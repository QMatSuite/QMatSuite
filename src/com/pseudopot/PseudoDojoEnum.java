/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.pseudopot;

public class PseudoDojoEnum {
	private PseudoDojoEnum() {
	}
	
	public static enum Sr_pbe_standard {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-sr-04_pbe_standard", "Ag.upf", 37.0, 41.0, 47.0, 4.0, 0.3, 0.6, -0.10),
		Al("nc-sr-04_pbe_standard", "Al.upf", 16.0, 20.0, 26.0, 2.0, 0.5, 1.3, -0.10),
		Ar("nc-sr-04_pbe_standard", "Ar.upf", 29.0, 33.0, 37.0, 2.0, 0.0, 1.2, null),
		As("nc-sr-04_pbe_standard", "As.upf", 38.0, 42.0, 48.0, 3.0, 0.4, 0.7, -0.00),
		Au("nc-sr-04_pbe_standard", "Au.upf", 32.0, 38.0, 44.0, 4.0, 1.3, 1.6, -0.10),
		B("nc-sr-04_pbe_standard", "B.upf", 34.0, 38.0, 44.0, 2.0, 0.3, 0.6, 0.00),
		Ba("nc-sr-04_pbe_standard", "Ba.upf", 18.0, 22.0, 28.0, 3.0, 0.9, 4.9, -0.10),
		Be("nc-sr-04_pbe_standard", "Be.upf", 38.0, 44.0, 50.0, 2.0, 1.4, 4.4, 0.20),
		Bi("nc-sr-04_pbe_standard", "Bi.upf", 29.0, 33.0, 37.0, 3.0, 0.2, 0.4, -0.00),
		Br("nc-sr-04_pbe_standard", "Br.upf", 19.0, 23.0, 29.0, 2.0, 0.0, 0.2, -0.20),
		C("nc-sr-04_pbe_standard", "C.upf", 37.0, 41.0, 45.0, 2.0, 0.1, 0.1, 0.10),
		Ca("nc-sr-04_pbe_standard", "Ca.upf", 28.0, 34.0, 38.0, 3.0, 0.1, 0.3, -0.20),
		Cd("nc-sr-04_pbe_standard", "Cd.upf", 47.0, 51.0, 57.0, 4.0, 1.1, 3.5, -0.00),
		Cl("nc-sr-04_pbe_standard", "Cl.upf", 25.0, 29.0, 33.0, 2.0, 0.8, 3.1, -0.30),
		Co("nc-sr-04_pbe_standard", "Co.upf", 42.0, 48.0, 54.0, 4.0, 1.0, 1.4, -0.00),
		Cr("nc-sr-04_pbe_standard", "Cr.upf", 43.0, 47.0, 55.0, 4.0, 10.5, 18.1, -0.00),
		Cs("nc-sr-04_pbe_standard", "Cs.upf", 19.0, 25.0, 29.0, 3.0, 0.1, 1.5, -0.40),
		Cu("nc-sr-04_pbe_standard", "Cu.upf", 42.0, 46.0, 52.0, 4.0, 0.5, 0.9, -0.10),
		F("nc-sr-04_pbe_standard", "F.upf", 36.0, 42.0, 48.0, 2.0, 0.1, 0.6, -0.60),
		Fe("nc-sr-04_pbe_standard", "Fe.upf", 41.0, 45.0, 53.0, 4.0, 5.6, 9.2, -0.10),
		Ga("nc-sr-04_pbe_standard", "Ga.upf", 36.0, 40.0, 46.0, 3.0, 0.5, 1.5, -0.00),
		Ge("nc-sr-04_pbe_standard", "Ge.upf", 35.0, 39.0, 45.0, 3.0, 0.5, 1.0, -0.00),
		H("nc-sr-04_pbe_standard", "H.upf", 32.0, 36.0, 42.0, 1.0, 0.1, 2.5, -0.00),
		He("nc-sr-04_pbe_standard", "He.upf", 39.0, 45.0, 49.0, 1.0, 0.0, 4.2, null),
		Hf("nc-sr-04_pbe_standard", "Hf.upf", 25.0, 29.0, 35.0, 4.0, 0.6, 0.8, -0.00),
		Hg("nc-sr-04_pbe_standard", "Hg.upf", 29.0, 33.0, 39.0, 4.0, 0.7, 7.2, null),
		I("nc-sr-04_pbe_standard", "I.upf", 31.0, 35.0, 41.0, 2.0, 0.4, 1.1, 0.00),
		In("nc-sr-04_pbe_standard", "In.upf", 31.0, 35.0, 41.0, 3.0, 0.1, 0.2, -0.10),
		Ir("nc-sr-04_pbe_standard", "Ir.upf", 30.0, 34.0, 40.0, 4.0, 1.5, 0.9, -0.20),
		K("nc-sr-04_pbe_standard", "K.upf", 33.0, 37.0, 43.0, 3.0, 0.2, 2.0, -0.30),
		Kr("nc-sr-04_pbe_standard", "Kr.upf", 22.0, 26.0, 34.0, 2.0, 0.0, 2.3, null),
		La("nc-sr-04_pbe_standard", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, -0.10),
		Li("nc-sr-04_pbe_standard", "Li.upf", 33.0, 37.0, 41.0, 2.0, 0.2, 1.9, -0.10),
		Lu("nc-sr-04_pbe_standard", "Lu.upf", 46.0, 50.0, 58.0, 5.0, 1.0, 2.2, null),
		Mg("nc-sr-04_pbe_standard", "Mg.upf", 38.0, 42.0, 48.0, 3.0, 0.4, 1.5, 0.00),
		Mn("nc-sr-04_pbe_standard", "Mn.upf", 42.0, 48.0, 54.0, 4.0, 8.0, 16.9, -0.10),
		Mo("nc-sr-04_pbe_standard", "Mo.upf", 36.0, 40.0, 46.0, 4.0, 1.4, 1.0, -0.10),
		N("nc-sr-04_pbe_standard", "N.upf", 36.0, 42.0, 48.0, 2.0, 0.2, 0.4, -0.10),
		Na("nc-sr-04_pbe_standard", "Na.upf", 38.0, 44.0, 48.0, 3.0, 0.4, 4.6, -0.00),
		Nb("nc-sr-04_pbe_standard", "Nb.upf", 37.0, 41.0, 49.0, 4.0, 1.3, 1.3, -0.00),
		Ne("nc-sr-04_pbe_standard", "Ne.upf", 30.0, 34.0, 40.0, 2.0, 0.0, 1.7, null),
		Ni("nc-sr-04_pbe_standard", "Ni.upf", 45.0, 49.0, 55.0, 4.0, 1.1, 1.5, -0.10),
		O("nc-sr-04_pbe_standard", "O.upf", 36.0, 42.0, 48.0, 2.0, 2.0, 6.5, -0.20),
		Os("nc-sr-04_pbe_standard", "Os.upf", 33.0, 37.0, 43.0, 4.0, 1.7, 0.9, -0.10),
		P("nc-sr-04_pbe_standard", "P.upf", 18.0, 22.0, 28.0, 2.0, 0.1, 0.3, -0.50),
		Pb("nc-sr-04_pbe_standard", "Pb.upf", 24.0, 28.0, 34.0, 3.0, 0.1, 0.1, -0.10),
		Pd("nc-sr-04_pbe_standard", "Pd.upf", 37.0, 41.0, 49.0, 3.0, 1.1, 1.3, -0.10),
		Po("nc-sr-04_pbe_standard", "Po.upf", 28.0, 32.0, 38.0, 3.0, 0.3, 0.5, null),
		Pt("nc-sr-04_pbe_standard", "Pt.upf", 38.0, 42.0, 50.0, 4.0, 0.6, 0.5, -0.20),
		Rb("nc-sr-04_pbe_standard", "Rb.upf", 19.0, 23.0, 29.0, 3.0, 0.2, 2.9, -0.40),
		Re("nc-sr-04_pbe_standard", "Re.upf", 30.0, 36.0, 42.0, 4.0, 0.7, 0.4, -0.10),
		Rh("nc-sr-04_pbe_standard", "Rh.upf", 40.0, 44.0, 50.0, 4.0, 2.6, 2.1, -0.00),
		Rn("nc-sr-04_pbe_standard", "Rn.upf", 32.0, 36.0, 42.0, 3.0, 0.0, 2.4, null),
		Ru("nc-sr-04_pbe_standard", "Ru.upf", 38.0, 42.0, 50.0, 4.0, 2.1, 1.5, -0.00),
		S("nc-sr-04_pbe_standard", "S.upf", 20.0, 26.0, 32.0, 2.0, 0.0, 0.1, -0.00),
		Sb("nc-sr-04_pbe_standard", "Sb.upf", 36.0, 40.0, 44.0, 3.0, 0.5, 1.0, 0.00),
		Sc("nc-sr-04_pbe_standard", "Sc.upf", 35.0, 39.0, 45.0, 4.0, 1.3, 2.8, -0.00),
		Se("nc-sr-04_pbe_standard", "Se.upf", 39.0, 43.0, 49.0, 3.0, 0.2, 0.5, -0.10),
		Si("nc-sr-04_pbe_standard", "Si.upf", 14.0, 18.0, 24.0, 2.0, 0.1, 0.2, -0.10),
		Sn("nc-sr-04_pbe_standard", "Sn.upf", 32.0, 36.0, 42.0, 3.0, 0.8, 1.8, 0.00),
		Sr("nc-sr-04_pbe_standard", "Sr.upf", 28.0, 34.0, 40.0, 3.0, 1.3, 6.1, -0.20),
		Ta("nc-sr-04_pbe_standard", "Ta.upf", 25.0, 29.0, 35.0, 4.0, 0.7, 0.6, -0.10),
		Tc("nc-sr-04_pbe_standard", "Tc.upf", 38.0, 42.0, 48.0, 4.0, 1.6, 1.1, -0.00),
		Te("nc-sr-04_pbe_standard", "Te.upf", 34.0, 40.0, 46.0, 3.0, 0.8, 1.6, 0.10),
		Ti("nc-sr-04_pbe_standard", "Ti.upf", 38.0, 42.0, 46.0, 4.0, 0.9, 1.3, -0.00),
		Tl("nc-sr-04_pbe_standard", "Tl.upf", 27.0, 31.0, 37.0, 3.0, 0.1, 0.2, -0.10),
		V("nc-sr-04_pbe_standard", "V.upf", 38.0, 42.0, 48.0, 4.0, 1.3, 1.6, -0.10),
		W("nc-sr-04_pbe_standard", "W.upf", 31.0, 37.0, 41.0, 4.0, 0.2, 0.1, -0.00),
		Xe("nc-sr-04_pbe_standard", "Xe.upf", 28.0, 34.0, 42.0, 2.0, 0.0, 2.5, null),
		Y("nc-sr-04_pbe_standard", "Y.upf", 30.0, 36.0, 42.0, 4.0, 1.0, 2.3, -0.10),
		Zn("nc-sr-04_pbe_standard", "Zn.upf", 38.0, 42.0, 48.0, 4.0, 0.3, 0.8, -0.10),
		Zr("nc-sr-04_pbe_standard", "Zr.upf", 29.0, 33.0, 49.0, 4.0, 0.8, 1.1, -0.00);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pbe_standard(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}//necessary
		public String getFileName() {return fileName;}//necessary
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Sr_pbe_stringent {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-sr-04_pbe_stringent", "Ag.upf", 37.0, 41.0, 47.0, 4.0, 0.3, 0.6, -0.10),
		Al("nc-sr-04_pbe_stringent", "Al.upf", 16.0, 20.0, 26.0, 2.0, 0.5, 1.3, -0.10),
		Ar("nc-sr-04_pbe_stringent", "Ar.upf", 29.0, 33.0, 37.0, 2.0, 0.0, 1.2, null),
		As("nc-sr-04_pbe_stringent", "As.upf", 48.0, 52.0, 58.0, 5.0, 0.1, 0.1, -0.00),
		Au("nc-sr-04_pbe_stringent", "Au.upf", 32.0, 38.0, 44.0, 4.0, 1.3, 1.6, -0.10),
		B("nc-sr-04_pbe_stringent", "B.upf", 34.0, 38.0, 44.0, 2.0, 0.3, 0.6, 0.00),
		Ba("nc-sr-04_pbe_stringent", "Ba.upf", 18.0, 22.0, 28.0, 3.0, 0.9, 4.8, -0.10),
		Be("nc-sr-04_pbe_stringent", "Be.upf", 49.0, 53.0, 59.0, 2.0, 0.9, 2.8, 0.20),
		Bi("nc-sr-04_pbe_stringent", "Bi.upf", 38.0, 44.0, 50.0, 5.0, 0.6, 1.1, -0.10),
		Br("nc-sr-04_pbe_stringent", "Br.upf", 34.0, 38.0, 44.0, 3.0, 0.0, 0.1, -0.20),
		C("nc-sr-04_pbe_stringent", "C.upf", 37.0, 41.0, 45.0, 2.0, 0.1, 0.1, 0.10),
		Ca("nc-sr-04_pbe_stringent", "Ca.upf", 28.0, 34.0, 38.0, 3.0, 0.1, 0.3, -0.20),
		Cd("nc-sr-04_pbe_stringent", "Cd.upf", 54.0, 60.0, 66.0, 4.0, 0.6, 2.0, -0.10),
		Cl("nc-sr-04_pbe_stringent", "Cl.upf", 25.0, 29.0, 33.0, 2.0, 0.8, 3.1, -0.30),
		Co("nc-sr-04_pbe_stringent", "Co.upf", 48.0, 52.0, 56.0, 4.0, 0.5, 0.7, -0.00),
		Cr("nc-sr-04_pbe_stringent", "Cr.upf", 56.0, 60.0, 66.0, 4.0, 1.1, 1.7, -0.10),
		Cs("nc-sr-04_pbe_stringent", "Cs.upf", 19.0, 25.0, 29.0, 3.0, 0.1, 1.5, -0.40),
		Cu("nc-sr-04_pbe_stringent", "Cu.upf", 48.0, 52.0, 60.0, 4.0, 0.5, 0.9, -0.10),
		F("nc-sr-04_pbe_stringent", "F.upf", 36.0, 42.0, 48.0, 2.0, 0.1, 0.6, -0.60),
		Fe("nc-sr-04_pbe_stringent", "Fe.upf", 55.0, 59.0, 65.0, 4.0, 2.1, 3.1, -0.10),
		Ga("nc-sr-04_pbe_stringent", "Ga.upf", 53.0, 57.0, 61.0, 5.0, 0.3, 0.9, 0.00),
		Ge("nc-sr-04_pbe_stringent", "Ge.upf", 56.0, 62.0, 68.0, 5.0, 0.1, 0.1, 0.00),
		H("nc-sr-04_pbe_stringent", "H.upf", 32.0, 36.0, 42.0, 1.0, 0.1, 2.5, -0.00),
		He("nc-sr-04_pbe_stringent", "He.upf", 39.0, 45.0, 49.0, 1.0, 0.0, 4.2, null),
		Hf("nc-sr-04_pbe_stringent", "Hf.upf", 62.0, 66.0, 72.0, 5.0, 0.3, 0.4, -0.00),
		Hg("nc-sr-04_pbe_stringent", "Hg.upf", 38.0, 44.0, 50.0, 4.0, 0.6, 6.4, null),
		I("nc-sr-04_pbe_stringent", "I.upf", 34.0, 38.0, 44.0, 3.0, 0.9, 2.9, 0.10),
		In("nc-sr-04_pbe_stringent", "In.upf", 37.0, 41.0, 49.0, 5.0, 0.4, 1.3, -0.00),
		Ir("nc-sr-04_pbe_stringent", "Ir.upf", 30.0, 34.0, 40.0, 4.0, 1.5, 0.9, -0.20),
		K("nc-sr-04_pbe_stringent", "K.upf", 33.0, 37.0, 43.0, 3.0, 0.2, 2.0, -0.30),
		Kr("nc-sr-04_pbe_stringent", "Kr.upf", 22.0, 26.0, 34.0, 2.0, 0.0, 2.3, null),
		La("nc-sr-04_pbe_stringent", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, -0.10),
		Li("nc-sr-04_pbe_stringent", "Li.upf", 44.0, 48.0, 52.0, 2.0, 0.1, 1.5, -0.10),
		Lu("nc-sr-04_pbe_stringent", "Lu.upf", 46.0, 50.0, 58.0, 5.0, 1.0, 2.2, null),
		Mg("nc-sr-04_pbe_stringent", "Mg.upf", 38.0, 42.0, 48.0, 3.0, 0.4, 1.5, 0.00),
		Mn("nc-sr-04_pbe_stringent", "Mn.upf", 61.0, 65.0, 69.0, 4.0, 1.1, 2.3, -0.00),
		Mo("nc-sr-04_pbe_stringent", "Mo.upf", 36.0, 40.0, 46.0, 4.0, 1.4, 1.0, -0.10),
		N("nc-sr-04_pbe_stringent", "N.upf", 36.0, 42.0, 48.0, 2.0, 0.2, 0.4, -0.10),
		Na("nc-sr-04_pbe_stringent", "Na.upf", 38.0, 44.0, 48.0, 3.0, 0.4, 4.6, -0.00),
		Nb("nc-sr-04_pbe_stringent", "Nb.upf", 37.0, 41.0, 49.0, 4.0, 1.3, 1.3, -0.00),
		Ne("nc-sr-04_pbe_stringent", "Ne.upf", 38.0, 44.0, 50.0, 2.0, 0.0, 5.2, null),
		Ni("nc-sr-04_pbe_stringent", "Ni.upf", 48.0, 52.0, 58.0, 4.0, 1.0, 1.5, -0.10),
		O("nc-sr-04_pbe_stringent", "O.upf", 42.0, 46.0, 52.0, 2.0, 1.3, 4.0, -0.20),
		Os("nc-sr-04_pbe_stringent", "Os.upf", 33.0, 37.0, 43.0, 4.0, 1.7, 0.9, -0.10),
		P("nc-sr-04_pbe_stringent", "P.upf", 18.0, 22.0, 28.0, 2.0, 0.1, 0.3, -0.50),
		Pb("nc-sr-04_pbe_stringent", "Pb.upf", 36.0, 44.0, 50.0, 5.0, 0.3, 0.6, -0.10),
		Pd("nc-sr-04_pbe_stringent", "Pd.upf", 37.0, 41.0, 49.0, 3.0, 1.1, 1.3, -0.10),
		Po("nc-sr-04_pbe_stringent", "Po.upf", 40.0, 44.0, 50.0, 5.0, 0.4, 0.7, null),
		Pt("nc-sr-04_pbe_stringent", "Pt.upf", 38.0, 42.0, 50.0, 4.0, 0.6, 0.5, -0.20),
		Rb("nc-sr-04_pbe_stringent", "Rb.upf", 19.0, 23.0, 29.0, 3.0, 0.2, 2.9, -0.40),
		Re("nc-sr-04_pbe_stringent", "Re.upf", 30.0, 36.0, 42.0, 4.0, 0.7, 0.4, -0.10),
		Rh("nc-sr-04_pbe_stringent", "Rh.upf", 40.0, 44.0, 50.0, 4.0, 2.6, 2.1, -0.00),
		Rn("nc-sr-04_pbe_stringent", "Rn.upf", 32.0, 36.0, 42.0, 3.0, 0.0, 2.4, null),
		Ru("nc-sr-04_pbe_stringent", "Ru.upf", 38.0, 42.0, 50.0, 4.0, 2.1, 1.5, -0.00),
		S("nc-sr-04_pbe_stringent", "S.upf", 20.0, 26.0, 32.0, 2.0, 0.0, 0.1, -0.00),
		Sb("nc-sr-04_pbe_stringent", "Sb.upf", 46.0, 50.0, 58.0, 5.0, 0.7, 1.3, 0.10),
		Sc("nc-sr-04_pbe_stringent", "Sc.upf", 35.0, 39.0, 45.0, 4.0, 1.3, 2.8, -0.00),
		Se("nc-sr-04_pbe_stringent", "Se.upf", 48.0, 52.0, 56.0, 5.0, 0.1, 0.2, -0.10),
		Si("nc-sr-04_pbe_stringent", "Si.upf", 14.0, 18.0, 24.0, 2.0, 0.1, 0.2, -0.10),
		Sn("nc-sr-04_pbe_stringent", "Sn.upf", 45.0, 51.0, 57.0, 5.0, 0.6, 1.4, 0.10),
		Sr("nc-sr-04_pbe_stringent", "Sr.upf", 28.0, 32.0, 36.0, 3.0, 1.3, 6.2, -0.20),
		Ta("nc-sr-04_pbe_stringent", "Ta.upf", 62.0, 66.0, 72.0, 5.0, 1.0, 0.9, -0.10),
		Tc("nc-sr-04_pbe_stringent", "Tc.upf", 38.0, 42.0, 48.0, 4.0, 1.6, 1.1, -0.00),
		Te("nc-sr-04_pbe_stringent", "Te.upf", 47.0, 51.0, 57.0, 5.0, 0.6, 1.2, 0.10),
		Ti("nc-sr-04_pbe_stringent", "Ti.upf", 38.0, 42.0, 46.0, 4.0, 0.9, 1.3, -0.00),
		Tl("nc-sr-04_pbe_stringent", "Tl.upf", 38.0, 44.0, 50.0, 5.0, 0.2, 0.8, -0.10),
		V("nc-sr-04_pbe_stringent", "V.upf", 38.0, 42.0, 48.0, 4.0, 1.3, 1.6, -0.10),
		W("nc-sr-04_pbe_stringent", "W.upf", 31.0, 37.0, 41.0, 4.0, 0.2, 0.1, -0.00),
		Xe("nc-sr-04_pbe_stringent", "Xe.upf", 28.0, 34.0, 42.0, 2.0, 0.0, 2.5, null),
		Y("nc-sr-04_pbe_stringent", "Y.upf", 30.0, 36.0, 42.0, 4.0, 1.0, 2.3, -0.10),
		Zn("nc-sr-04_pbe_stringent", "Zn.upf", 38.0, 42.0, 48.0, 4.0, 0.3, 0.8, -0.10),
		Zr("nc-sr-04_pbe_stringent", "Zr.upf", 29.0, 33.0, 49.0, 4.0, 0.8, 1.1, -0.00);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pbe_stringent(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Sr_pbesol_standard {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-sr-04_pbesol_standard", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-sr-04_pbesol_standard", "Al.upf", 16.0, 20.0, 26.0, 2.0, null, null, null),
		Ar("nc-sr-04_pbesol_standard", "Ar.upf", 29.0, 33.0, 37.0, 2.0, null, null, null),
		As("nc-sr-04_pbesol_standard", "As.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Au("nc-sr-04_pbesol_standard", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-sr-04_pbesol_standard", "B.upf", 34.0, 38.0, 44.0, 2.0, null, null, null),
		Ba("nc-sr-04_pbesol_standard", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-sr-04_pbesol_standard", "Be.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Bi("nc-sr-04_pbesol_standard", "Bi.upf", 29.0, 33.0, 37.0, 3.0, null, null, null),
		Br("nc-sr-04_pbesol_standard", "Br.upf", 19.0, 23.0, 29.0, 2.0, null, null, null),
		C("nc-sr-04_pbesol_standard", "C.upf", 37.0, 41.0, 45.0, 2.0, null, null, null),
		Ca("nc-sr-04_pbesol_standard", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-sr-04_pbesol_standard", "Cd.upf", 47.0, 51.0, 57.0, 4.0, null, null, null),
		Cl("nc-sr-04_pbesol_standard", "Cl.upf", 25.0, 29.0, 33.0, 2.0, null, null, null),
		Co("nc-sr-04_pbesol_standard", "Co.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Cr("nc-sr-04_pbesol_standard", "Cr.upf", 43.0, 47.0, 55.0, 4.0, null, null, null),
		Cs("nc-sr-04_pbesol_standard", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-sr-04_pbesol_standard", "Cu.upf", 42.0, 46.0, 52.0, 4.0, null, null, null),
		F("nc-sr-04_pbesol_standard", "F.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Fe("nc-sr-04_pbesol_standard", "Fe.upf", 41.0, 45.0, 53.0, 4.0, null, null, null),
		Ga("nc-sr-04_pbesol_standard", "Ga.upf", 36.0, 40.0, 46.0, 3.0, null, null, null),
		Ge("nc-sr-04_pbesol_standard", "Ge.upf", 35.0, 39.0, 45.0, 3.0, null, null, null),
		H("nc-sr-04_pbesol_standard", "H.upf", 32.0, 36.0, 42.0, 1.0, null, null, null),
		He("nc-sr-04_pbesol_standard", "He.upf", 39.0, 45.0, 49.0, 1.0, null, null, null),
		Hf("nc-sr-04_pbesol_standard", "Hf.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Hg("nc-sr-04_pbesol_standard", "Hg.upf", 29.0, 33.0, 39.0, 4.0, null, null, null),
		I("nc-sr-04_pbesol_standard", "I.upf", 31.0, 35.0, 41.0, 2.0, null, null, null),
		In("nc-sr-04_pbesol_standard", "In.upf", 31.0, 35.0, 41.0, 3.0, null, null, null),
		Ir("nc-sr-04_pbesol_standard", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-sr-04_pbesol_standard", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-sr-04_pbesol_standard", "Kr.upf", 22.0, 26.0, 34.0, 2.0, null, null, null),
		La("nc-sr-04_pbesol_standard", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, null),
		Li("nc-sr-04_pbesol_standard", "Li.upf", 33.0, 37.0, 41.0, 2.0, null, null, null),
		Lu("nc-sr-04_pbesol_standard", "Lu.upf", 46.0, 50.0, 58.0, 5.0, null, null, null),
		Mg("nc-sr-04_pbesol_standard", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-sr-04_pbesol_standard", "Mn.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Mo("nc-sr-04_pbesol_standard", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-sr-04_pbesol_standard", "N.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Na("nc-sr-04_pbesol_standard", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-sr-04_pbesol_standard", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-sr-04_pbesol_standard", "Ne.upf", 30.0, 34.0, 40.0, 2.0, null, null, null),
		Ni("nc-sr-04_pbesol_standard", "Ni.upf", 45.0, 49.0, 55.0, 4.0, null, null, null),
		O("nc-sr-04_pbesol_standard", "O.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Os("nc-sr-04_pbesol_standard", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-sr-04_pbesol_standard", "P.upf", 18.0, 22.0, 28.0, 2.0, null, null, null),
		Pb("nc-sr-04_pbesol_standard", "Pb.upf", 24.0, 28.0, 34.0, 3.0, null, null, null),
		Pd("nc-sr-04_pbesol_standard", "Pd.upf", 37.0, 41.0, 49.0, 3.0, null, null, null),
		Po("nc-sr-04_pbesol_standard", "Po.upf", 28.0, 32.0, 38.0, 3.0, null, null, null),
		Pt("nc-sr-04_pbesol_standard", "Pt.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		Rb("nc-sr-04_pbesol_standard", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-sr-04_pbesol_standard", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-sr-04_pbesol_standard", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-sr-04_pbesol_standard", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-sr-04_pbesol_standard", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-sr-04_pbesol_standard", "S.upf", 20.0, 26.0, 32.0, 2.0, null, null, null),
		Sb("nc-sr-04_pbesol_standard", "Sb.upf", 36.0, 40.0, 44.0, 3.0, null, null, null),
		Sc("nc-sr-04_pbesol_standard", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-sr-04_pbesol_standard", "Se.upf", 39.0, 43.0, 49.0, 3.0, null, null, null),
		Si("nc-sr-04_pbesol_standard", "Si.upf", 14.0, 18.0, 24.0, 2.0, null, null, null),
		Sn("nc-sr-04_pbesol_standard", "Sn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Sr("nc-sr-04_pbesol_standard", "Sr.upf", 28.0, 34.0, 40.0, 3.0, null, null, null),
		Ta("nc-sr-04_pbesol_standard", "Ta.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Tc("nc-sr-04_pbesol_standard", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-sr-04_pbesol_standard", "Te.upf", 34.0, 40.0, 46.0, 3.0, null, null, null),
		Ti("nc-sr-04_pbesol_standard", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-sr-04_pbesol_standard", "Tl.upf", 27.0, 31.0, 37.0, 3.0, null, null, null),
		V("nc-sr-04_pbesol_standard", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-sr-04_pbesol_standard", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-sr-04_pbesol_standard", "Xe.upf", 28.0, 34.0, 42.0, 2.0, null, null, null),
		Y("nc-sr-04_pbesol_standard", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-sr-04_pbesol_standard", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-sr-04_pbesol_standard", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pbesol_standard(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Sr_pbesol_stringent {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org

		Ag("nc-sr-04_pbesol_stringent", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-sr-04_pbesol_stringent", "Al.upf", 16.0, 20.0, 26.0, 2.0, null, null, null),
		Ar("nc-sr-04_pbesol_stringent", "Ar.upf", 29.0, 33.0, 37.0, 2.0, null, null, null),
		As("nc-sr-04_pbesol_stringent", "As.upf", 48.0, 52.0, 58.0, 5.0, null, null, null),
		Au("nc-sr-04_pbesol_stringent", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-sr-04_pbesol_stringent", "B.upf", 34.0, 38.0, 44.0, 2.0, null, null, null),
		Ba("nc-sr-04_pbesol_stringent", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-sr-04_pbesol_stringent", "Be.upf", 49.0, 53.0, 59.0, 2.0, null, null, null),
		Bi("nc-sr-04_pbesol_stringent", "Bi.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		Br("nc-sr-04_pbesol_stringent", "Br.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		C("nc-sr-04_pbesol_stringent", "C.upf", 37.0, 41.0, 45.0, 2.0, null, null, null),
		Ca("nc-sr-04_pbesol_stringent", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-sr-04_pbesol_stringent", "Cd.upf", 54.0, 60.0, 66.0, 4.0, null, null, null),
		Cl("nc-sr-04_pbesol_stringent", "Cl.upf", 25.0, 29.0, 33.0, 2.0, null, null, null),
		Co("nc-sr-04_pbesol_stringent", "Co.upf", 48.0, 52.0, 56.0, 4.0, null, null, null),
		Cr("nc-sr-04_pbesol_stringent", "Cr.upf", 56.0, 60.0, 66.0, 4.0, null, null, null),
		Cs("nc-sr-04_pbesol_stringent", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-sr-04_pbesol_stringent", "Cu.upf", 48.0, 52.0, 60.0, 4.0, null, null, null),
		F("nc-sr-04_pbesol_stringent", "F.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Fe("nc-sr-04_pbesol_stringent", "Fe.upf", 55.0, 59.0, 65.0, 4.0, null, null, null),
		Ga("nc-sr-04_pbesol_stringent", "Ga.upf", 53.0, 57.0, 61.0, 5.0, null, null, null),
		Ge("nc-sr-04_pbesol_stringent", "Ge.upf", 56.0, 62.0, 68.0, 5.0, null, null, null),
		H("nc-sr-04_pbesol_stringent", "H.upf", 32.0, 36.0, 42.0, 1.0, null, null, null),
		He("nc-sr-04_pbesol_stringent", "He.upf", 39.0, 45.0, 49.0, 1.0, null, null, null),
		Hf("nc-sr-04_pbesol_stringent", "Hf.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Hg("nc-sr-04_pbesol_stringent", "Hg.upf", 38.0, 44.0, 50.0, 4.0, null, null, null),
		I("nc-sr-04_pbesol_stringent", "I.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		In("nc-sr-04_pbesol_stringent", "In.upf", 37.0, 41.0, 49.0, 5.0, null, null, null),
		Ir("nc-sr-04_pbesol_stringent", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-sr-04_pbesol_stringent", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-sr-04_pbesol_stringent", "Kr.upf", 22.0, 26.0, 34.0, 2.0, null, null, null),
		La("nc-sr-04_pbesol_stringent", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, null),
		Li("nc-sr-04_pbesol_stringent", "Li.upf", 44.0, 48.0, 52.0, 2.0, null, null, null),
		Lu("nc-sr-04_pbesol_stringent", "Lu.upf", 46.0, 50.0, 58.0, 5.0, null, null, null),
		Mg("nc-sr-04_pbesol_stringent", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-sr-04_pbesol_stringent", "Mn.upf", 61.0, 65.0, 69.0, 4.0, null, null, null),
		Mo("nc-sr-04_pbesol_stringent", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-sr-04_pbesol_stringent", "N.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Na("nc-sr-04_pbesol_stringent", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-sr-04_pbesol_stringent", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-sr-04_pbesol_stringent", "Ne.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Ni("nc-sr-04_pbesol_stringent", "Ni.upf", 48.0, 52.0, 58.0, 4.0, null, null, null),
		O("nc-sr-04_pbesol_stringent", "O.upf", 42.0, 46.0, 52.0, 2.0, null, null, null),
		Os("nc-sr-04_pbesol_stringent", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-sr-04_pbesol_stringent", "P.upf", 18.0, 22.0, 28.0, 2.0, null, null, null),
		Pb("nc-sr-04_pbesol_stringent", "Pb.upf", 36.0, 44.0, 50.0, 5.0, null, null, null),
		Pd("nc-sr-04_pbesol_stringent", "Pd.upf", 37.0, 41.0, 49.0, 3.0, null, null, null),
		Po("nc-sr-04_pbesol_stringent", "Po.upf", 40.0, 44.0, 50.0, 5.0, null, null, null),
		Pt("nc-sr-04_pbesol_stringent", "Pt.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		Rb("nc-sr-04_pbesol_stringent", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-sr-04_pbesol_stringent", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-sr-04_pbesol_stringent", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-sr-04_pbesol_stringent", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-sr-04_pbesol_stringent", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-sr-04_pbesol_stringent", "S.upf", 20.0, 26.0, 32.0, 2.0, null, null, null),
		Sb("nc-sr-04_pbesol_stringent", "Sb.upf", 46.0, 50.0, 58.0, 5.0, null, null, null),
		Sc("nc-sr-04_pbesol_stringent", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-sr-04_pbesol_stringent", "Se.upf", 48.0, 52.0, 56.0, 5.0, null, null, null),
		Si("nc-sr-04_pbesol_stringent", "Si.upf", 14.0, 18.0, 24.0, 2.0, null, null, null),
		Sn("nc-sr-04_pbesol_stringent", "Sn.upf", 45.0, 51.0, 57.0, 5.0, null, null, null),
		Sr("nc-sr-04_pbesol_stringent", "Sr.upf", 28.0, 32.0, 36.0, 3.0, null, null, null),
		Ta("nc-sr-04_pbesol_stringent", "Ta.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Tc("nc-sr-04_pbesol_stringent", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-sr-04_pbesol_stringent", "Te.upf", 47.0, 51.0, 57.0, 5.0, null, null, null),
		Ti("nc-sr-04_pbesol_stringent", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-sr-04_pbesol_stringent", "Tl.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		V("nc-sr-04_pbesol_stringent", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-sr-04_pbesol_stringent", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-sr-04_pbesol_stringent", "Xe.upf", 28.0, 34.0, 42.0, 2.0, null, null, null),
		Y("nc-sr-04_pbesol_stringent", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-sr-04_pbesol_stringent", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-sr-04_pbesol_stringent", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pbesol_stringent(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Sr_pw_standard {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-sr-04_pw_standard", "Ag.upf", 39.0, 43.0, 49.0, 4.0, 0.1, 0.2, null),
		Al("nc-sr-04_pw_standard", "Al.upf", 16.0, 22.0, 28.0, 2.0, 1.0, 2.2, null),
		Ar("nc-sr-04_pw_standard", "Ar.upf", 29.0, 33.0, 37.0, 2.0, 0.0, 0.3, null),
		As("nc-sr-04_pw_standard", "As.upf", 34.0, 40.0, 44.0, 3.0, 0.3, 0.4, null),
		Au("nc-sr-04_pw_standard", "Au.upf", 28.0, 32.0, 38.0, 4.0, 2.0, 1.9, null),
		B("nc-sr-04_pw_standard", "B.upf", 34.0, 38.0, 44.0, 2.0, 0.3, 0.4, null),
		Ba("nc-sr-04_pw_standard", "Ba.upf", 18.0, 22.0, 26.0, 3.0, 1.0, 5.4, null),
		Be("nc-sr-04_pw_standard", "Be.upf", 38.0, 44.0, 50.0, 2.0, 0.5, 1.4, null),
		Bi("nc-sr-04_pw_standard", "Bi.upf", 31.0, 35.0, 41.0, 3.0, 0.1, 0.1, null),
		Br("nc-sr-04_pw_standard", "Br.upf", 18.0, 22.0, 28.0, 2.0, 0.2, 0.6, null),
		C("nc-sr-04_pw_standard", "C.upf", 37.0, 41.0, 45.0, 2.0, 2.2, 2.6, null),
		Ca("nc-sr-04_pw_standard", "Ca.upf", 30.0, 36.0, 42.0, 3.0, 0.5, 2.2, null),
		Cd("nc-sr-04_pw_standard", "Cd.upf", 47.0, 51.0, 59.0, 4.0, 1.9, 4.0, null),
		Cl("nc-sr-04_pw_standard", "Cl.upf", 24.0, 28.0, 34.0, 2.0, 0.7, 1.9, null),
		Cr("nc-sr-04_pw_standard", "Cr.upf", 43.0, 47.0, 55.0, 4.0, 1.5, 1.4, null),
		Cu("nc-sr-04_pw_standard", "Cu.upf", 38.0, 42.0, 46.0, 4.0, 0.6, 0.8, null),
		F("nc-sr-04_pw_standard", "F.upf", 34.0, 42.0, 46.0, 2.0, 0.1, 0.6, null),
		Fe("nc-sr-04_pw_standard", "Fe.upf", 39.0, 45.0, 47.0, 4.0, 1.8, 2.0, null),
		Ga("nc-sr-04_pw_standard", "Ga.upf", 36.0, 40.0, 46.0, 3.0, 0.7, 1.7, null),
		H("nc-sr-04_pw_standard", "H.upf", 31.0, 37.0, 43.0, 1.0, 0.1, 2.1, null),
		He("nc-sr-04_pw_standard", "He.upf", 39.0, 45.0, 50.0, 1.0, 0.0, 1.0, null),
		Hf("nc-sr-04_pw_standard", "Hf.upf", 25.0, 29.0, 35.0, 4.0, 5.9, 7.2, null),
		Hg("nc-sr-04_pw_standard", "Hg.upf", 26.0, 30.0, 34.0, 4.0, 1.1, 2.5, null),
		I("nc-sr-04_pw_standard", "I.upf", 31.0, 35.0, 41.0, 2.0, 0.7, 1.7, null),
		In("nc-sr-04_pw_standard", "In.upf", 31.0, 35.0, 41.0, 3.0, 0.5, 1.2, null),
		Ir("nc-sr-04_pw_standard", "Ir.upf", 24.0, 28.0, 32.0, 4.0, 2.3, 1.2, null),
		K("nc-sr-04_pw_standard", "K.upf", 32.0, 36.0, 42.0, 3.0, 0.1, 1.4, null),
		Kr("nc-sr-04_pw_standard", "Kr.upf", 22.0, 26.0, 36.0, 2.0, 0.0, 0.4, null),
		Li("nc-sr-04_pw_standard", "Li.upf", 33.0, 37.0, 41.0, 2.0, 0.1, 1.5, null),
		Mg("nc-sr-04_pw_standard", "Mg.upf", 38.0, 42.0, 48.0, 3.0, 0.5, 1.7, null),
		Mo("nc-sr-04_pw_standard", "Mo.upf", 36.0, 40.0, 46.0, 4.0, 1.4, 0.9, null),
		N("nc-sr-04_pw_standard", "N.upf", 36.0, 42.0, 48.0, 2.0, 1.8, 3.3, null),
		Na("nc-sr-04_pw_standard", "Na.upf", 38.0, 44.0, 48.0, 3.0, 0.2, 2.0, null),
		Nb("nc-sr-04_pw_standard", "Nb.upf", 37.0, 41.0, 49.0, 4.0, 1.2, 1.1, null),
		Ne("nc-sr-04_pw_standard", "Ne.upf", 44.0, 44.0, 52.0, 2.0, 0.0, 1.0, null),
		Os("nc-sr-04_pw_standard", "Os.upf", 33.0, 37.0, 43.0, 4.0, 3.1, 1.5, null),
		P("nc-sr-04_pw_standard", "P.upf", 18.0, 24.0, 30.0, 2.0, 1.8, 3.3, null),
		Pb("nc-sr-04_pw_standard", "Pb.upf", 24.0, 28.0, 34.0, 3.0, 0.3, 0.6, null),
		Pd("nc-sr-04_pw_standard", "Pd.upf", 37.0, 41.0, 47.0, 3.0, 1.4, 1.3, null),
		Po("nc-sr-04_pw_standard", "Po.upf", 28.0, 32.0, 38.0, 3.0, 0.2, 0.3, null),
		Pt("nc-sr-04_pw_standard", "Pt.upf", 34.0, 38.0, 42.0, 4.0, 1.4, 0.9, null),
		Rb("nc-sr-04_pw_standard", "Rb.upf", 17.0, 21.0, 25.0, 3.0, 0.2, 1.8, null),
		Re("nc-sr-04_pw_standard", "Re.upf", 30.0, 36.0, 42.0, 4.0, 2.6, 1.4, null),
		Rh("nc-sr-04_pw_standard", "Rh.upf", 40.0, 44.0, 50.0, 4.0, 2.7, 1.9, null),
		Rn("nc-sr-04_pw_standard", "Rn.upf", 28.0, 32.0, 36.0, 3.0, 0.1, 0.7, null),
		Ru("nc-sr-04_pw_standard", "Ru.upf", 40.0, 44.0, 50.0, 4.0, 2.3, 1.4, null),
		S("nc-sr-04_pw_standard", "S.upf", 21.0, 27.0, 33.0, 2.0, 0.1, 0.1, null),
		Sb("nc-sr-04_pw_standard", "Sb.upf", 36.0, 42.0, 48.0, 3.0, 0.0, 0.1, null),
		Sc("nc-sr-04_pw_standard", "Sc.upf", 35.0, 39.0, 45.0, 4.0, 1.0, 2.3, null),
		Se("nc-sr-04_pw_standard", "Se.upf", 39.0, 43.0, 49.0, 3.0, 0.1, 0.1, null),
		Si("nc-sr-04_pw_standard", "Si.upf", 12.0, 16.0, 22.0, 2.0, 1.6, 2.6, null),
		Sn("nc-sr-04_pw_standard", "Sn.upf", 32.0, 36.0, 42.0, 3.0, 0.0, 0.1, null),
		Sr("nc-sr-04_pw_standard", "Sr.upf", 28.0, 34.0, 40.0, 3.0, 1.0, 4.7, null),
		Ta("nc-sr-04_pw_standard", "Ta.upf", 25.0, 29.0, 35.0, 4.0, 3.7, 3.0, null),
		Tc("nc-sr-04_pw_standard", "Tc.upf", 38.0, 44.0, 50.0, 4.0, 1.7, 1.1, null),
		Te("nc-sr-04_pw_standard", "Te.upf", 34.0, 40.0, 46.0, 3.0, 0.6, 1.0, null),
		Ti("nc-sr-04_pw_standard", "Ti.upf", 38.0, 42.0, 48.0, 4.0, 0.7, 1.0, null),
		Tl("nc-sr-04_pw_standard", "Tl.upf", 27.0, 31.0, 37.0, 3.0, 0.4, 1.1, null),
		V("nc-sr-04_pw_standard", "V.upf", 38.0, 42.0, 48.0, 4.0, 1.2, 1.4, null),
		W("nc-sr-04_pw_standard", "W.upf", 29.0, 35.0, 41.0, 4.0, 3.7, 2.2, null),
		Xe("nc-sr-04_pw_standard", "Xe.upf", 29.0, 35.0, 43.0, 2.0, 0.1, 0.9, null),
		Y("nc-sr-04_pw_standard", "Y.upf", 30.0, 36.0, 42.0, 4.0, 1.1, 2.4, null),
		Zn("nc-sr-04_pw_standard", "Zn.upf", 30.0, 36.0, 42.0, 4.0, 0.6, 1.2, null),
		Zr("nc-sr-04_pw_standard", "Zr.upf", 29.0, 35.0, 41.0, 4.0, 0.7, 0.9, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pw_standard(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Sr_pw_stringent {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-sr-04_pw_stringent", "Ag.upf", 39.0, 43.0, 49.0, 4.0, 0.1, 0.2, null),
		Al("nc-sr-04_pw_stringent", "Al.upf", 16.0, 22.0, 28.0, 2.0, 1.0, 2.2, null),
		Ar("nc-sr-04_pw_stringent", "Ar.upf", 29.0, 33.0, 37.0, 2.0, 0.0, 0.3, null),
		As("nc-sr-04_pw_stringent", "As.upf", 44.0, 50.0, 54.0, 5.0, 0.1, 0.2, null),
		Au("nc-sr-04_pw_stringent", "Au.upf", 28.0, 32.0, 38.0, 4.0, 2.0, 1.9, null),
		B("nc-sr-04_pw_stringent", "B.upf", 34.0, 38.0, 44.0, 2.0, 0.3, 0.4, null),
		Ba("nc-sr-04_pw_stringent", "Ba.upf", 18.0, 22.0, 26.0, 3.0, 1.0, 5.4, null),
		Be("nc-sr-04_pw_stringent", "Be.upf", 49.0, 53.0, 59.0, 2.0, 0.2, 0.6, null),
		Bi("nc-sr-04_pw_stringent", "Bi.upf", 32.0, 36.0, 40.0, 5.0, 0.7, 1.1, null),
		C("nc-sr-04_pw_stringent", "C.upf", 37.0, 41.0, 45.0, 2.0, 2.2, 2.6, null),
		Ca("nc-sr-04_pw_stringent", "Ca.upf", 30.0, 36.0, 42.0, 3.0, 0.5, 2.2, null),
		Cd("nc-sr-04_pw_stringent", "Cd.upf", 47.0, 51.0, 59.0, 4.0, 1.9, 4.0, null),
		Cl("nc-sr-04_pw_stringent", "Cl.upf", 24.0, 28.0, 34.0, 2.0, 0.7, 1.9, null),
		Cr("nc-sr-04_pw_stringent", "Cr.upf", 56.0, 60.0, 66.0, 4.0, 0.1, 0.1, null),
		Cu("nc-sr-04_pw_stringent", "Cu.upf", 50.0, 56.0, 62.0, 4.0, 0.5, 0.8, null),
		F("nc-sr-04_pw_stringent", "F.upf", 34.0, 42.0, 46.0, 2.0, 0.1, 0.6, null),
		Fe("nc-sr-04_pw_stringent", "Fe.upf", 65.0, 69.0, 73.0, 4.0, 0.3, 0.3, null),
		Ga("nc-sr-04_pw_stringent", "Ga.upf", 45.0, 53.0, 57.0, 5.0, 0.3, 0.7, null),
		H("nc-sr-04_pw_stringent", "H.upf", 31.0, 37.0, 43.0, 1.0, 0.1, 2.1, null),
		He("nc-sr-04_pw_stringent", "He.upf", 39.0, 45.0, 50.0, 1.0, 0.0, 1.0, null),
		Hf("nc-sr-04_pw_stringent", "Hf.upf", 62.0, 66.0, 72.0, 5.0, 0.1, 0.2, null),
		Hg("nc-sr-04_pw_stringent", "Hg.upf", 26.0, 30.0, 34.0, 4.0, 1.1, 2.5, null),
		In("nc-sr-04_pw_stringent", "In.upf", 33.0, 37.0, 41.0, 5.0, 0.3, 0.8, null),
		Ir("nc-sr-04_pw_stringent", "Ir.upf", 24.0, 28.0, 32.0, 4.0, 2.3, 1.2, null),
		K("nc-sr-04_pw_stringent", "K.upf", 32.0, 36.0, 42.0, 3.0, 0.1, 1.4, null),
		Kr("nc-sr-04_pw_stringent", "Kr.upf", 22.0, 26.0, 36.0, 2.0, 0.0, 0.4, null),
		Li("nc-sr-04_pw_stringent", "Li.upf", 44.0, 48.0, 52.0, 2.0, 0.1, 1.4, null),
		Mg("nc-sr-04_pw_stringent", "Mg.upf", 38.0, 42.0, 48.0, 3.0, 0.5, 1.7, null),
		Mo("nc-sr-04_pw_stringent", "Mo.upf", 36.0, 40.0, 46.0, 4.0, 1.4, 0.9, null),
		N("nc-sr-04_pw_stringent", "N.upf", 36.0, 42.0, 48.0, 2.0, 1.8, 3.3, null),
		Na("nc-sr-04_pw_stringent", "Na.upf", 38.0, 44.0, 48.0, 3.0, 0.2, 2.0, null),
		Nb("nc-sr-04_pw_stringent", "Nb.upf", 37.0, 41.0, 49.0, 4.0, 1.2, 1.1, null),
		Ne("nc-sr-04_pw_stringent", "Ne.upf", 36.0, 40.0, 44.0, 2.0, 0.0, 0.9, null),
		Os("nc-sr-04_pw_stringent", "Os.upf", 33.0, 37.0, 43.0, 4.0, 3.1, 1.5, null),
		P("nc-sr-04_pw_stringent", "P.upf", 18.0, 24.0, 30.0, 2.0, 1.8, 3.3, null),
		Pb("nc-sr-04_pw_stringent", "Pb.upf", 32.0, 36.0, 40.0, 5.0, 0.1, 0.1, null),
		Pd("nc-sr-04_pw_stringent", "Pd.upf", 37.0, 41.0, 47.0, 3.0, 1.4, 1.3, null),
		Po("nc-sr-04_pw_stringent", "Po.upf", 30.0, 36.0, 42.0, 5.0, 0.9, 1.3, null),
		Pt("nc-sr-04_pw_stringent", "Pt.upf", 34.0, 38.0, 42.0, 4.0, 1.4, 0.9, null),
		Rb("nc-sr-04_pw_stringent", "Rb.upf", 17.0, 21.0, 25.0, 3.0, 0.2, 1.8, null),
		Re("nc-sr-04_pw_stringent", "Re.upf", 30.0, 36.0, 42.0, 4.0, 2.6, 1.4, null),
		Rh("nc-sr-04_pw_stringent", "Rh.upf", 40.0, 44.0, 50.0, 4.0, 2.7, 1.9, null),
		Rn("nc-sr-04_pw_stringent", "Rn.upf", 28.0, 32.0, 36.0, 3.0, 0.1, 0.7, null),
		Ru("nc-sr-04_pw_stringent", "Ru.upf", 40.0, 44.0, 50.0, 4.0, 2.3, 1.4, null),
		S("nc-sr-04_pw_stringent", "S.upf", 21.0, 27.0, 33.0, 2.0, 0.1, 0.1, null),
		Sb("nc-sr-04_pw_stringent", "Sb.upf", 40.0, 44.0, 50.0, 5.0, 0.7, 1.2, null),
		Sc("nc-sr-04_pw_stringent", "Sc.upf", 35.0, 39.0, 45.0, 4.0, 1.0, 2.3, null),
		Se("nc-sr-04_pw_stringent", "Se.upf", 48.0, 52.0, 56.0, 5.0, 0.0, 0.0, null),
		Si("nc-sr-04_pw_stringent", "Si.upf", 12.0, 16.0, 22.0, 2.0, 1.6, 2.6, null),
		Sn("nc-sr-04_pw_stringent", "Sn.upf", 38.0, 43.0, 49.0, 5.0, 0.4, 0.8, null),
		Sr("nc-sr-04_pw_stringent", "Sr.upf", 28.0, 34.0, 40.0, 3.0, 1.0, 4.7, null),
		Ta("nc-sr-04_pw_stringent", "Ta.upf", 62.0, 66.0, 72.0, 5.0, 0.6, 0.5, null),
		Tc("nc-sr-04_pw_stringent", "Tc.upf", 38.0, 44.0, 50.0, 4.0, 1.7, 1.1, null),
		Te("nc-sr-04_pw_stringent", "Te.upf", 39.0, 43.0, 49.0, 5.0, 0.8, 1.4, null),
		Ti("nc-sr-04_pw_stringent", "Ti.upf", 38.0, 42.0, 48.0, 4.0, 0.7, 1.0, null),
		Tl("nc-sr-04_pw_stringent", "Tl.upf", 34.0, 38.0, 42.0, 5.0, 0.4, 1.0, null),
		V("nc-sr-04_pw_stringent", "V.upf", 38.0, 42.0, 48.0, 4.0, 1.2, 1.4, null),
		W("nc-sr-04_pw_stringent", "W.upf", 58.0, 62.0, 68.0, 5.0, 1.5, 0.9, null),
		Xe("nc-sr-04_pw_stringent", "Xe.upf", 29.0, 35.0, 43.0, 2.0, 0.1, 0.9, null),
		Y("nc-sr-04_pw_stringent", "Y.upf", 30.0, 36.0, 42.0, 4.0, 1.1, 2.4, null),
		Zn("nc-sr-04_pw_stringent", "Zn.upf", 30.0, 36.0, 42.0, 4.0, 0.6, 1.2, null),
		Zr("nc-sr-04_pw_stringent", "Zr.upf", 29.0, 35.0, 41.0, 4.0, 0.7, 0.9, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Sr_pw_stringent(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Fr_pbe_standard {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-fr-04_pbe_standard", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-fr-04_pbe_standard", "Al.upf", 16.0, 20.0, 26.0, 2.0, null, null, null),
		Ar("nc-fr-04_pbe_standard", "Ar.upf", 29.0, 33.0, 37.0, 2.0, null, null, null),
		As("nc-fr-04_pbe_standard", "As.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Au("nc-fr-04_pbe_standard", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-fr-04_pbe_standard", "B.upf", 34.0, 38.0, 44.0, 2.0, null, null, null),
		Ba("nc-fr-04_pbe_standard", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-fr-04_pbe_standard", "Be.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Bi("nc-fr-04_pbe_standard", "Bi.upf", 29.0, 33.0, 37.0, 3.0, null, null, null),
		Br("nc-fr-04_pbe_standard", "Br.upf", 19.0, 23.0, 29.0, 2.0, null, null, null),
		C("nc-fr-04_pbe_standard", "C.upf", 37.0, 41.0, 45.0, 2.0, null, null, null),
		Ca("nc-fr-04_pbe_standard", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-fr-04_pbe_standard", "Cd.upf", 47.0, 51.0, 57.0, 4.0, null, null, null),
		Cl("nc-fr-04_pbe_standard", "Cl.upf", 25.0, 29.0, 33.0, 2.0, null, null, null),
		Co("nc-fr-04_pbe_standard", "Co.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Cr("nc-fr-04_pbe_standard", "Cr.upf", 43.0, 47.0, 55.0, 4.0, null, null, null),
		Cs("nc-fr-04_pbe_standard", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-fr-04_pbe_standard", "Cu.upf", 42.0, 46.0, 52.0, 4.0, null, null, null),
		F("nc-fr-04_pbe_standard", "F.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Fe("nc-fr-04_pbe_standard", "Fe.upf", 41.0, 45.0, 53.0, 4.0, null, null, null),
		Ga("nc-fr-04_pbe_standard", "Ga.upf", 36.0, 40.0, 46.0, 3.0, null, null, null),
		Ge("nc-fr-04_pbe_standard", "Ge.upf", 35.0, 39.0, 45.0, 3.0, null, null, null),
		H("nc-fr-04_pbe_standard", "H.upf", 32.0, 36.0, 42.0, 1.0, null, null, null),
		He("nc-fr-04_pbe_standard", "He.upf", 39.0, 45.0, 49.0, 1.0, null, null, null),
		Hf("nc-fr-04_pbe_standard", "Hf.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Hg("nc-fr-04_pbe_standard", "Hg.upf", 29.0, 33.0, 39.0, 4.0, null, null, null),
		I("nc-fr-04_pbe_standard", "I.upf", 31.0, 35.0, 41.0, 2.0, null, null, null),
		In("nc-fr-04_pbe_standard", "In.upf", 31.0, 35.0, 41.0, 3.0, null, null, null),
		Ir("nc-fr-04_pbe_standard", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-fr-04_pbe_standard", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-fr-04_pbe_standard", "Kr.upf", 22.0, 26.0, 34.0, 2.0, null, null, null),
		Li("nc-fr-04_pbe_standard", "Li.upf", 33.0, 37.0, 41.0, 2.0, null, null, null),
		Mg("nc-fr-04_pbe_standard", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-fr-04_pbe_standard", "Mn.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Mo("nc-fr-04_pbe_standard", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-fr-04_pbe_standard", "N.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Na("nc-fr-04_pbe_standard", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-fr-04_pbe_standard", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-fr-04_pbe_standard", "Ne.upf", 30.0, 34.0, 40.0, 2.0, null, null, null),
		Ni("nc-fr-04_pbe_standard", "Ni.upf", 47.0, 49.0, 57.0, 4.0, null, null, null),
		O("nc-fr-04_pbe_standard", "O.upf", 36.0, 42.0, 48.0, 2.0, null, null, null),
		Os("nc-fr-04_pbe_standard", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-fr-04_pbe_standard", "P.upf", 18.0, 22.0, 28.0, 2.0, null, null, null),
		Pb("nc-fr-04_pbe_standard", "Pb.upf", 24.0, 28.0, 34.0, 3.0, null, null, null),
		Pd("nc-fr-04_pbe_standard", "Pd.upf", 37.0, 41.0, 47.0, 3.0, null, null, null),
		Po("nc-fr-04_pbe_standard", "Po.upf", 28.0, 32.0, 38.0, 3.0, null, null, null),
		Pt("nc-fr-04_pbe_standard", "Pt.upf", 36.0, 42.0, 48.0, 4.0, null, null, null),
		Rb("nc-fr-04_pbe_standard", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-fr-04_pbe_standard", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-fr-04_pbe_standard", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-fr-04_pbe_standard", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-fr-04_pbe_standard", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-fr-04_pbe_standard", "S.upf", 20.0, 26.0, 32.0, 2.0, null, null, null),
		Sb("nc-fr-04_pbe_standard", "Sb.upf", 36.0, 40.0, 44.0, 3.0, null, null, null),
		Sc("nc-fr-04_pbe_standard", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-fr-04_pbe_standard", "Se.upf", 39.0, 43.0, 49.0, 3.0, null, null, null),
		Si("nc-fr-04_pbe_standard", "Si.upf", 14.0, 18.0, 24.0, 2.0, null, null, null),
		Sn("nc-fr-04_pbe_standard", "Sn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Sr("nc-fr-04_pbe_standard", "Sr.upf", 28.0, 34.0, 40.0, 3.0, null, null, null),
		Ta("nc-fr-04_pbe_standard", "Ta.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Tc("nc-fr-04_pbe_standard", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-fr-04_pbe_standard", "Te.upf", 34.0, 40.0, 46.0, 3.0, null, null, null),
		Ti("nc-fr-04_pbe_standard", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-fr-04_pbe_standard", "Tl.upf", 27.0, 31.0, 37.0, 3.0, null, null, null),
		V("nc-fr-04_pbe_standard", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-fr-04_pbe_standard", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-fr-04_pbe_standard", "Xe.upf", 28.0, 34.0, 42.0, 2.0, null, null, null),
		Y("nc-fr-04_pbe_standard", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-fr-04_pbe_standard", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-fr-04_pbe_standard", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Fr_pbe_standard(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Fr_pbe_stringent {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-fr-04_pbe_stringent", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-fr-04_pbe_stringent", "Al.upf", null, null, null, null, null, null, null),
		Ar("nc-fr-04_pbe_stringent", "Ar.upf", null, null, null, null, null, null, null),
		As("nc-fr-04_pbe_stringent", "As.upf", 48.0, 52.0, 58.0, 5.0, null, null, null),
		Au("nc-fr-04_pbe_stringent", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-fr-04_pbe_stringent", "B.upf", null, null, null, null, null, null, null),
		Ba("nc-fr-04_pbe_stringent", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-fr-04_pbe_stringent", "Be.upf", 49.0, 53.0, 59.0, 2.0, null, null, null),
		Bi("nc-fr-04_pbe_stringent", "Bi.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		Br("nc-fr-04_pbe_stringent", "Br.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		C("nc-fr-04_pbe_stringent", "C.upf", null, null, null, null, null, null, null),
		Ca("nc-fr-04_pbe_stringent", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-fr-04_pbe_stringent", "Cd.upf", 54.0, 60.0, 66.0, 4.0, null, null, null),
		Cl("nc-fr-04_pbe_stringent", "Cl.upf", null, null, null, null, null, null, null),
		Co("nc-fr-04_pbe_stringent", "Co.upf", 48.0, 52.0, 56.0, 4.0, null, null, null),
		Cr("nc-fr-04_pbe_stringent", "Cr.upf", 56.0, 60.0, 66.0, 4.0, null, null, null),
		Cs("nc-fr-04_pbe_stringent", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-fr-04_pbe_stringent", "Cu.upf", 48.0, 52.0, 60.0, 4.0, null, null, null),
		F("nc-fr-04_pbe_stringent", "F.upf", null, null, null, null, null, null, null),
		Fe("nc-fr-04_pbe_stringent", "Fe.upf", 55.0, 59.0, 65.0, 4.0, null, null, null),
		Ga("nc-fr-04_pbe_stringent", "Ga.upf", 53.0, 57.0, 61.0, 5.0, null, null, null),
		Ge("nc-fr-04_pbe_stringent", "Ge.upf", null, null, null, 5.0, null, null, null),
		H("nc-fr-04_pbe_stringent", "H.upf", null, null, null, null, null, null, null),
		He("nc-fr-04_pbe_stringent", "He.upf", null, null, null, null, null, null, null),
		Hf("nc-fr-04_pbe_stringent", "Hf.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Hg("nc-fr-04_pbe_stringent", "Hg.upf", 38.0, 44.0, 50.0, 4.0, null, null, null),
		I("nc-fr-04_pbe_stringent", "I.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		In("nc-fr-04_pbe_stringent", "In.upf", 37.0, 41.0, 49.0, 5.0, null, null, null),
		Ir("nc-fr-04_pbe_stringent", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-fr-04_pbe_stringent", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-fr-04_pbe_stringent", "Kr.upf", null, null, null, null, null, null, null),
		La("nc-fr-04_pbe_stringent", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, null),
		Li("nc-fr-04_pbe_stringent", "Li.upf", null, null, null, 2.0, null, null, null),
		Lu("nc-fr-04_pbe_stringent", "Lu.upf", 46.0, 50.0, 58.0, 5.0, null, null, null),
		Mg("nc-fr-04_pbe_stringent", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-fr-04_pbe_stringent", "Mn.upf", 61.0, 65.0, 69.0, 4.0, null, null, null),
		Mo("nc-fr-04_pbe_stringent", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-fr-04_pbe_stringent", "N.upf", null, null, null, null, null, null, null),
		Na("nc-fr-04_pbe_stringent", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-fr-04_pbe_stringent", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-fr-04_pbe_stringent", "Ne.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Ni("nc-fr-04_pbe_stringent", "Ni.upf", 48.0, 52.0, 58.0, 4.0, null, null, null),
		O("nc-fr-04_pbe_stringent", "O.upf", 42.0, 46.0, 52.0, 2.0, null, null, null),
		Os("nc-fr-04_pbe_stringent", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-fr-04_pbe_stringent", "P.upf", null, null, null, null, null, null, null),
		Pb("nc-fr-04_pbe_stringent", "Pb.upf", 36.0, 44.0, 50.0, 5.0, null, null, null),
		Pd("nc-fr-04_pbe_stringent", "Pd.upf", 37.0, 41.0, 47.0, 3.0, null, null, null),
		Po("nc-fr-04_pbe_stringent", "Po.upf", 40.0, 44.0, 50.0, 5.0, null, null, null),
		Pt("nc-fr-04_pbe_stringent", "Pt.upf", 36.0, 42.0, 48.0, 4.0, null, null, null),
		Rb("nc-fr-04_pbe_stringent", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-fr-04_pbe_stringent", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-fr-04_pbe_stringent", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-fr-04_pbe_stringent", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-fr-04_pbe_stringent", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-fr-04_pbe_stringent", "S.upf", null, null, null, null, null, null, null),
		Sb("nc-fr-04_pbe_stringent", "Sb.upf", null, null, null, 5.0, null, null, null),
		Sc("nc-fr-04_pbe_stringent", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-fr-04_pbe_stringent", "Se.upf", 48.0, 52.0, 56.0, 5.0, null, null, null),
		Si("nc-fr-04_pbe_stringent", "Si.upf", null, null, null, null, null, null, null),
		Sn("nc-fr-04_pbe_stringent", "Sn.upf", 45.0, 51.0, 57.0, 5.0, null, null, null),
		Sr("nc-fr-04_pbe_stringent", "Sr.upf", 28.0, 32.0, 36.0, 3.0, null, null, null),
		Ta("nc-fr-04_pbe_stringent", "Ta.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Tc("nc-fr-04_pbe_stringent", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-fr-04_pbe_stringent", "Te.upf", null, null, null, 5.0, null, null, null),
		Ti("nc-fr-04_pbe_stringent", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-fr-04_pbe_stringent", "Tl.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		V("nc-fr-04_pbe_stringent", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-fr-04_pbe_stringent", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-fr-04_pbe_stringent", "Xe.upf", null, null, null, null, null, null, null),
		Y("nc-fr-04_pbe_stringent", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-fr-04_pbe_stringent", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-fr-04_pbe_stringent", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Fr_pbe_stringent(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Fr_pbesol_standard {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org
		
		Ag("nc-fr-04_pbesol_standard", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-fr-04_pbesol_standard", "Al.upf", null, null, null, null, null, null, null),
		Ar("nc-fr-04_pbesol_standard", "Ar.upf", null, null, null, null, null, null, null),
		As("nc-fr-04_pbesol_standard", "As.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Au("nc-fr-04_pbesol_standard", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-fr-04_pbesol_standard", "B.upf", null, null, null, null, null, null, null),
		Ba("nc-fr-04_pbesol_standard", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-fr-04_pbesol_standard", "Be.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Bi("nc-fr-04_pbesol_standard", "Bi.upf", 29.0, 33.0, 37.0, 3.0, null, null, null),
		Br("nc-fr-04_pbesol_standard", "Br.upf", null, null, null, null, null, null, null),
		C("nc-fr-04_pbesol_standard", "C.upf", null, null, null, null, null, null, null),
		Ca("nc-fr-04_pbesol_standard", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-fr-04_pbesol_standard", "Cd.upf", 47.0, 51.0, 57.0, 4.0, null, null, null),
		Cl("nc-fr-04_pbesol_standard", "Cl.upf", null, null, null, null, null, null, null),
		Co("nc-fr-04_pbesol_standard", "Co.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Cr("nc-fr-04_pbesol_standard", "Cr.upf", 43.0, 47.0, 55.0, 4.0, null, null, null),
		Cs("nc-fr-04_pbesol_standard", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-fr-04_pbesol_standard", "Cu.upf", 42.0, 46.0, 52.0, 4.0, null, null, null),
		F("nc-fr-04_pbesol_standard", "F.upf", null, null, null, null, null, null, null),
		Fe("nc-fr-04_pbesol_standard", "Fe.upf", 41.0, 45.0, 53.0, 4.0, null, null, null),
		Ga("nc-fr-04_pbesol_standard", "Ga.upf", 36.0, 40.0, 46.0, 3.0, null, null, null),
		Ge("nc-fr-04_pbesol_standard", "Ge.upf", 35.0, 39.0, 45.0, 3.0, null, null, null),
		H("nc-fr-04_pbesol_standard", "H.upf", null, null, null, null, null, null, null),
		He("nc-fr-04_pbesol_standard", "He.upf", null, null, null, null, null, null, null),
		Hf("nc-fr-04_pbesol_standard", "Hf.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Hg("nc-fr-04_pbesol_standard", "Hg.upf", 29.0, 33.0, 39.0, 4.0, null, null, null),
		I("nc-fr-04_pbesol_standard", "I.upf", null, null, null, null, null, null, null),
		In("nc-fr-04_pbesol_standard", "In.upf", 31.0, 35.0, 41.0, 3.0, null, null, null),
		Ir("nc-fr-04_pbesol_standard", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-fr-04_pbesol_standard", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-fr-04_pbesol_standard", "Kr.upf", null, null, null, null, null, null, null),
		La("nc-fr-04_pbesol_standard", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, null),
		Li("nc-fr-04_pbesol_standard", "Li.upf", 33.0, 37.0, 41.0, 2.0, null, null, null),
		Mg("nc-fr-04_pbesol_standard", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-fr-04_pbesol_standard", "Mn.upf", 42.0, 48.0, 54.0, 4.0, null, null, null),
		Mo("nc-fr-04_pbesol_standard", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-fr-04_pbesol_standard", "N.upf", null, null, null, null, null, null, null),
		Na("nc-fr-04_pbesol_standard", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-fr-04_pbesol_standard", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-fr-04_pbesol_standard", "Ne.upf", null, null, null, null, null, null, null),
		Ni("nc-fr-04_pbesol_standard", "Ni.upf", 45.0, 49.0, 55.0, 4.0, null, null, null),
		O("nc-fr-04_pbesol_standard", "O.upf", null, null, null, null, null, null, null),
		Os("nc-fr-04_pbesol_standard", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-fr-04_pbesol_standard", "P.upf", null, null, null, null, null, null, null),
		Pb("nc-fr-04_pbesol_standard", "Pb.upf", 24.0, 28.0, 34.0, 3.0, null, null, null),
		Pd("nc-fr-04_pbesol_standard", "Pd.upf", 37.0, 41.0, 49.0, 3.0, null, null, null),
		Po("nc-fr-04_pbesol_standard", "Po.upf", 28.0, 32.0, 38.0, 3.0, null, null, null),
		Pt("nc-fr-04_pbesol_standard", "Pt.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		Rb("nc-fr-04_pbesol_standard", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-fr-04_pbesol_standard", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-fr-04_pbesol_standard", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-fr-04_pbesol_standard", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-fr-04_pbesol_standard", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-fr-04_pbesol_standard", "S.upf", null, null, null, null, null, null, null),
		Sb("nc-fr-04_pbesol_standard", "Sb.upf", 36.0, 40.0, 44.0, 3.0, null, null, null),
		Sc("nc-fr-04_pbesol_standard", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-fr-04_pbesol_standard", "Se.upf", 39.0, 43.0, 49.0, 3.0, null, null, null),
		Si("nc-fr-04_pbesol_standard", "Si.upf", null, null, null, null, null, null, null),
		Sn("nc-fr-04_pbesol_standard", "Sn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Sr("nc-fr-04_pbesol_standard", "Sr.upf", 28.0, 34.0, 40.0, 3.0, null, null, null),
		Ta("nc-fr-04_pbesol_standard", "Ta.upf", 25.0, 29.0, 35.0, 4.0, null, null, null),
		Tc("nc-fr-04_pbesol_standard", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-fr-04_pbesol_standard", "Te.upf", 34.0, 40.0, 46.0, 3.0, null, null, null),
		Ti("nc-fr-04_pbesol_standard", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-fr-04_pbesol_standard", "Tl.upf", 27.0, 31.0, 37.0, 3.0, null, null, null),
		V("nc-fr-04_pbesol_standard", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-fr-04_pbesol_standard", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-fr-04_pbesol_standard", "Xe.upf", null, null, null, null, null, null, null),
		Y("nc-fr-04_pbesol_standard", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-fr-04_pbesol_standard", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-fr-04_pbesol_standard", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Fr_pbesol_standard(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	public static enum Fr_pbesol_stringent {
		//For licenses and acknowledgments please go to the website below
		//http://www.pseudo-dojo.org

		Ag("nc-fr-04_pbesol_stringent", "Ag.upf", 37.0, 41.0, 47.0, 4.0, null, null, null),
		Al("nc-fr-04_pbesol_stringent", "Al.upf", null, null, null, null, null, null, null),
		Ar("nc-fr-04_pbesol_stringent", "Ar.upf", null, null, null, null, null, null, null),
		As("nc-fr-04_pbesol_stringent", "As.upf", 48.0, 52.0, 58.0, 5.0, null, null, null),
		Au("nc-fr-04_pbesol_stringent", "Au.upf", 32.0, 38.0, 44.0, 4.0, null, null, null),
		B("nc-fr-04_pbesol_stringent", "B.upf", null, null, null, null, null, null, null),
		Ba("nc-fr-04_pbesol_stringent", "Ba.upf", 18.0, 22.0, 28.0, 3.0, null, null, null),
		Be("nc-fr-04_pbesol_stringent", "Be.upf", 49.0, 53.0, 59.0, 2.0, null, null, null),
		Bi("nc-fr-04_pbesol_stringent", "Bi.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		Br("nc-fr-04_pbesol_stringent", "Br.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		C("nc-fr-04_pbesol_stringent", "C.upf", null, null, null, null, null, null, null),
		Ca("nc-fr-04_pbesol_stringent", "Ca.upf", 28.0, 34.0, 38.0, 3.0, null, null, null),
		Cd("nc-fr-04_pbesol_stringent", "Cd.upf", 54.0, 60.0, 66.0, 4.0, null, null, null),
		Cl("nc-fr-04_pbesol_stringent", "Cl.upf", null, null, null, null, null, null, null),
		Co("nc-fr-04_pbesol_stringent", "Co.upf", 48.0, 52.0, 56.0, 4.0, null, null, null),
		Cr("nc-fr-04_pbesol_stringent", "Cr.upf", 56.0, 60.0, 66.0, 4.0, null, null, null),
		Cs("nc-fr-04_pbesol_stringent", "Cs.upf", 19.0, 25.0, 29.0, 3.0, null, null, null),
		Cu("nc-fr-04_pbesol_stringent", "Cu.upf", 48.0, 52.0, 60.0, 4.0, null, null, null),
		F("nc-fr-04_pbesol_stringent", "F.upf", null, null, null, null, null, null, null),
		Fe("nc-fr-04_pbesol_stringent", "Fe.upf", 55.0, 59.0, 65.0, 4.0, null, null, null),
		Ga("nc-fr-04_pbesol_stringent", "Ga.upf", 53.0, 57.0, 61.0, 5.0, null, null, null),
		Ge("nc-fr-04_pbesol_stringent", "Ge.upf", 56.0, 62.0, 68.0, 5.0, null, null, null),
		H("nc-fr-04_pbesol_stringent", "H.upf", null, null, null, null, null, null, null),
		He("nc-fr-04_pbesol_stringent", "He.upf", null, null, null, null, null, null, null),
		Hf("nc-fr-04_pbesol_stringent", "Hf.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Hg("nc-fr-04_pbesol_stringent", "Hg.upf", 38.0, 44.0, 50.0, 4.0, null, null, null),
		I("nc-fr-04_pbesol_stringent", "I.upf", 34.0, 38.0, 44.0, 3.0, null, null, null),
		In("nc-fr-04_pbesol_stringent", "In.upf", 37.0, 41.0, 49.0, 5.0, null, null, null),
		Ir("nc-fr-04_pbesol_stringent", "Ir.upf", 30.0, 34.0, 40.0, 4.0, null, null, null),
		K("nc-fr-04_pbesol_stringent", "K.upf", 33.0, 37.0, 43.0, 3.0, null, null, null),
		Kr("nc-fr-04_pbesol_stringent", "Kr.upf", null, null, null, null, null, null, null),
		La("nc-fr-04_pbesol_stringent", "La.upf", 50.0, 55.0, 65.0, 4.0, null, null, null),
		Li("nc-fr-04_pbesol_stringent", "Li.upf", 44.0, 48.0, 52.0, 2.0, null, null, null),
		Mg("nc-fr-04_pbesol_stringent", "Mg.upf", 38.0, 42.0, 48.0, 3.0, null, null, null),
		Mn("nc-fr-04_pbesol_stringent", "Mn.upf", 61.0, 65.0, 69.0, 4.0, null, null, null),
		Mo("nc-fr-04_pbesol_stringent", "Mo.upf", 36.0, 40.0, 46.0, 4.0, null, null, null),
		N("nc-fr-04_pbesol_stringent", "N.upf", null, null, null, null, null, null, null),
		Na("nc-fr-04_pbesol_stringent", "Na.upf", 38.0, 44.0, 48.0, 3.0, null, null, null),
		Nb("nc-fr-04_pbesol_stringent", "Nb.upf", 37.0, 41.0, 49.0, 4.0, null, null, null),
		Ne("nc-fr-04_pbesol_stringent", "Ne.upf", 38.0, 44.0, 50.0, 2.0, null, null, null),
		Ni("nc-fr-04_pbesol_stringent", "Ni.upf", 48.0, 52.0, 58.0, 4.0, null, null, null),
		O("nc-fr-04_pbesol_stringent", "O.upf", 42.0, 46.0, 52.0, 2.0, null, null, null),
		Os("nc-fr-04_pbesol_stringent", "Os.upf", 33.0, 37.0, 43.0, 4.0, null, null, null),
		P("nc-fr-04_pbesol_stringent", "P.upf", null, null, null, null, null, null, null),
		Pb("nc-fr-04_pbesol_stringent", "Pb.upf", 36.0, 44.0, 50.0, 5.0, null, null, null),
		Pd("nc-fr-04_pbesol_stringent", "Pd.upf", 37.0, 41.0, 49.0, 3.0, null, null, null),
		Po("nc-fr-04_pbesol_stringent", "Po.upf", 40.0, 44.0, 50.0, 5.0, null, null, null),
		Pt("nc-fr-04_pbesol_stringent", "Pt.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		Rb("nc-fr-04_pbesol_stringent", "Rb.upf", 19.0, 23.0, 29.0, 3.0, null, null, null),
		Re("nc-fr-04_pbesol_stringent", "Re.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Rh("nc-fr-04_pbesol_stringent", "Rh.upf", 40.0, 44.0, 50.0, 4.0, null, null, null),
		Rn("nc-fr-04_pbesol_stringent", "Rn.upf", 32.0, 36.0, 42.0, 3.0, null, null, null),
		Ru("nc-fr-04_pbesol_stringent", "Ru.upf", 38.0, 42.0, 50.0, 4.0, null, null, null),
		S("nc-fr-04_pbesol_stringent", "S.upf", null, null, null, null, null, null, null),
		Sb("nc-fr-04_pbesol_stringent", "Sb.upf", 46.0, 50.0, 58.0, 5.0, null, null, null),
		Sc("nc-fr-04_pbesol_stringent", "Sc.upf", 35.0, 39.0, 45.0, 4.0, null, null, null),
		Se("nc-fr-04_pbesol_stringent", "Se.upf", 48.0, 52.0, 56.0, 5.0, null, null, null),
		Si("nc-fr-04_pbesol_stringent", "Si.upf", null, null, null, null, null, null, null),
		Sn("nc-fr-04_pbesol_stringent", "Sn.upf", 45.0, 51.0, 57.0, 5.0, null, null, null),
		Sr("nc-fr-04_pbesol_stringent", "Sr.upf", 28.0, 32.0, 36.0, 3.0, null, null, null),
		Ta("nc-fr-04_pbesol_stringent", "Ta.upf", 62.0, 66.0, 72.0, 5.0, null, null, null),
		Tc("nc-fr-04_pbesol_stringent", "Tc.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Te("nc-fr-04_pbesol_stringent", "Te.upf", 47.0, 51.0, 57.0, 5.0, null, null, null),
		Ti("nc-fr-04_pbesol_stringent", "Ti.upf", 38.0, 42.0, 46.0, 4.0, null, null, null),
		Tl("nc-fr-04_pbesol_stringent", "Tl.upf", 38.0, 44.0, 50.0, 5.0, null, null, null),
		V("nc-fr-04_pbesol_stringent", "V.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		W("nc-fr-04_pbesol_stringent", "W.upf", 31.0, 37.0, 41.0, 4.0, null, null, null),
		Xe("nc-fr-04_pbesol_stringent", "Xe.upf", null, null, null, null, null, null, null),
		Y("nc-fr-04_pbesol_stringent", "Y.upf", 30.0, 36.0, 42.0, 4.0, null, null, null),
		Zn("nc-fr-04_pbesol_stringent", "Zn.upf", 38.0, 42.0, 48.0, 4.0, null, null, null),
		Zr("nc-fr-04_pbesol_stringent", "Zr.upf", 29.0, 33.0, 49.0, 4.0, null, null, null);

		private final String folderName;
		private final String fileName;
		private final Double lowCut;//Hartree
		private final Double normalCut;//Hartree
		private final Double highCut;//Hartree
		private final Double nValenceShells;
		private final Double deltaGauge;//meV
		private final Double renormalizedDeltaGauge;
		private final Double gbrv;//Average FCC BCC GBRV test (%)

	    private Fr_pbesol_stringent(String folderName, String fileName, Double lowCut, Double normalCut, Double highCut, Double nValenceShells,
	    		Double deltaGauge, Double renormalizedDeltaGauge, Double gbrv) {
	    	this.folderName = folderName;
	    	this.fileName = fileName;
	    	this.lowCut = lowCut;
	    	this.normalCut = normalCut;
	    	this.highCut = highCut;
	    	this.nValenceShells = nValenceShells;
	    	this.deltaGauge = deltaGauge;
	    	this.renormalizedDeltaGauge = renormalizedDeltaGauge;
	    	this.gbrv = gbrv;
	    }

		public String getFolderName() {return folderName;}
		public String getFileName() {return fileName;}
		public Double getLowCut() {return lowCut;}
		public Double getNormalCut() {return normalCut;}
		public Double getHighCut() {return highCut;}
		public Double getnValenceShells() {return nValenceShells;}
		public Double getDeltaGauge() {return deltaGauge;}
		public Double getRenormalizedDeltaGauge() {return renormalizedDeltaGauge;}
		public Double getGbrv() {return gbrv;}

	}
	
	
}
