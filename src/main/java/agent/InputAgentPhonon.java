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
package agent;

import com.consts.Constants.EnumKUnitBands;

public class InputAgentPhonon extends InputAgentK{
	/**
	 * 
	 */
	private static final long serialVersionUID = -514978220626504472L;
	
//	public WrapperInteger itermax0;//from turbo_lanczos.x, and number of coefficients read in turbo_spectrum.x
//	public WrapperEnum enumPolar;
	public WrapperInteger nq1,
	nq2,
	nq3;
//	public WrapperEnum enumExtrap;
//	public WrapperEnum enumEUnit;
	public WrapperDouble tr2_ph;
//	estart,
//	eend,
//	de;
//	public WrapperBoolean eels;
	
	
	public InputAgentPhonon() {
//		itermax0 =  new WrapperInteger(500);
//		enumPolar = new WrapperEnum(EnumPolarizability.alpha_xx);
//		itermax =  new WrapperInteger(500);
//		enumExtrap = new WrapperEnum(EnumExtrapolation.no);
//		enumEUnit = new WrapperEnum(EnumTddftUnitEnergy.Ry);
		tr2_ph = new WrapperDouble(1E-12);//in Ry
		nq1 = new WrapperInteger(4,true);
		nq2 = new WrapperInteger(4,true);
		nq3 = new WrapperInteger(4,true);
//		estart = new WrapperDouble(0.0);
//		eend = new WrapperDouble(2.5);
//		de = new WrapperDouble(0.001);
//		eels =  new WrapperBoolean(false);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		if(inputStr==null || inputStr.isEmpty()) {return false;}
		//return true for detecting keyword
		int startInd;
		startInd = inputStr.toUpperCase().indexOf("/");
		if(startInd==-1) {startInd=0;}
		
		listKPoints.clear();
		
		String[] lines = inputStr.substring(startInd).split("\\R");
		
		//unit of atomic positions
		this.enumKUnit.setValue(EnumKUnitBands.crystal_b);

		getKPointsLine(listKPoints,lines[0]);
		
		//load k points
		for(int i=1;i<lines.length;i++) {
			if(lines[i].trim().isEmpty()) {continue;}//skip empty lines
			if(!getKPointsLine(listKPoints,lines[i])) {break;}//break if the line does not contain atomic positions
		}
		return true;
	}
}
