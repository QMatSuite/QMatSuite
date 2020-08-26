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

import com.consts.Constants.EnumAsr;
import com.consts.Constants.EnumKUnitBands;

import core.agent.InputAgentK;
import core.agent.WrapperBoolean;
import core.agent.WrapperDouble;
import core.agent.WrapperEnum;
import core.agent.WrapperInteger;

public class InputAgentPhonon extends InputAgentK{
	/**
	 * 
	 */
	private static final long serialVersionUID = -514978220626504472L;
	
	//ph.x
	public WrapperBoolean ldisp;//true for grid, false for gamma only
	public WrapperDouble tr2_ph;
	public WrapperInteger nq1,
	nq2,
	nq3;
	public WrapperBoolean epsil,
	lraman;
	public WrapperDouble eth_rps,
	eth_ns,
	dek;
	//q2r.x and matdyn.x
	public WrapperEnum asr;
	//matdyn.x
	public WrapperBoolean dos;
	public WrapperInteger nk1,
	nk2,
	nk3;
	public InputAgentPhonon() {
		//ph.x
		ldisp = new WrapperBoolean(false);
		tr2_ph = new WrapperDouble(1E-12);//in Ry
		nq1 = new WrapperInteger(4);//no QE default
		nq2 = new WrapperInteger(4);
		nq3 = new WrapperInteger(4);
		epsil = new WrapperBoolean(false);
		lraman = new WrapperBoolean(false);
		eth_rps = new WrapperDouble(1E-9);
		eth_ns = new WrapperDouble(1E-12);
		dek = new WrapperDouble(1E-3);
		//q2r.x and matdyn.x
		asr = new WrapperEnum(EnumAsr.no);
		//matdyn.x
		dos = new WrapperBoolean(true,true);//not the same as QE default, so always write
		nk1 = new WrapperInteger(8);//required if not dos, no QE default
		nk2 = new WrapperInteger(8);
		nk3 = new WrapperInteger(8);
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
