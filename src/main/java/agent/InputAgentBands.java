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

import java.io.IOException;
import java.util.ArrayList;

import com.consts.Constants.EnumKUnitBands;
import app.input.Kpoint;
import core.agent.InputAgentK;
import core.agent.WrapperEnum;
import core.agent.WrapperInteger;


public class InputAgentBands extends InputAgentK{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3123568374548375634L;
	
	public WrapperInteger intNBands;
	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//************to be compatible with v0.1.0
		//************to change this class, must append to the following manually!
		//************later restored to default
		
		//for loading after serialization
		//in.defaultReadObject();//this does not work!
		java.io.ObjectInputStream.GetField gf = in.readFields();
		
		intNBands = (WrapperInteger) gf.get("intNBands", new WrapperInteger(null));
		//try to get the two fields that belong originally to this class
		//but in v0.2.0 moved to InputAgentK class
		try {
			enumKUnit = (WrapperEnum) gf.get("enumKUnit", new WrapperEnum(EnumKUnitBands.crystal_b));
			listKPoints = (ArrayList<Kpoint>) gf.get("listKPoints", new ArrayList<Kpoint>());
		}catch(Exception e) {
			
		}
	}
	
	public InputAgentBands() {
		intNBands = new WrapperInteger(null);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		if(inputStr==null || inputStr.isEmpty()) {return false;}
		//return true for detecting keyword
		int startInd;
		startInd = inputStr.toUpperCase().indexOf("K_POINTS");
		if(startInd==-1) {return false;}
		
		listKPoints.clear();
		
		String[] lines = inputStr.substring(startInd).split("\\R");
		//unit of atomic positions
		if(lines[0].toLowerCase().contains("crystal_b")) {
			this.enumKUnit.setValue(EnumKUnitBands.crystal_b);
		}else if(lines[0].toLowerCase().contains("tpiba_b")) {
			this.enumKUnit.setValue(EnumKUnitBands.tpiba_b);
		}else {
			this.enumKUnit.setValue(EnumKUnitBands.tpiba_b);//not necessarily the default of QE
		}
		//load k points
		for(int i=1;i<lines.length;i++) {//starting from 1 to skip the line containing "ATOMIC_POSITIONS"
			if(lines[i].trim().isEmpty()) {continue;}//skip empty lines
			if(!getKPointsLine(listKPoints,lines[i])) {break;}//break if the line does not contain atomic positions
		}
		return true;
	}
	
}
