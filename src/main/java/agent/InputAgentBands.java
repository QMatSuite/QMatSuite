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

import java.util.ArrayList;
import com.consts.Constants.EnumKUnitBands;
import app.input.Kpoint;


public class InputAgentBands extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3123568374548375634L;
	public WrapperEnum enumKUnit;
	public WrapperInteger intNBands;
	public ArrayList<Kpoint> listKPoints;
	
	public InputAgentBands() {
		enumKUnit = new WrapperEnum(EnumKUnitBands.crystal_b);
		intNBands = new WrapperInteger(null);
		listKPoints = new ArrayList<Kpoint>();
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
	private boolean getKPointsLine(ArrayList<Kpoint> listKPoints, String inputLine) {
		//false means not containing atomic positions
		String[] splitted = inputLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length == 1) {return true;}//skip the line with one number (total k points) without breaking
		if(splitted.length < 4) {return false;}
		try {
			Double kx = Double.valueOf(splitted[0].trim());
			Double ky = Double.valueOf(splitted[1].trim());
			Double kz = Double.valueOf(splitted[2].trim());
			Integer nk = Integer.valueOf(splitted[3].trim());
			
			if(kx==null || ky == null || kz == null || nk == null) {return false;}
			
			String strLabel="";
			if(splitted.length >=5 && splitted[4].contains("!")) {
				strLabel = splitted[4].trim().replace('!', '\0');
			}
			listKPoints.add(new Kpoint(strLabel, kx, ky, kz, nk));
			return true;
		}
		catch(IllegalArgumentException e){
			//e.printStackTrace();
			return false;
		}
	}
	public String genAgentSummary() {
		String msg="";
		if(listKPoints==null || listKPoints.isEmpty()) {msg+="No k-point detected.\n";}
		else {
			msg+="K-points read:\n";
			for(int i=0;i<listKPoints.size();i++) {
				msg+=(listKPoints.get(i).getLabel()+": "+Double.toString(listKPoints.get(i).getKx())+","+Double.toString(listKPoints.get(i).getKy())+","+
						Double.toString(listKPoints.get(i).getKz())+","+Integer.toString(listKPoints.get(i).getNk())+"\n");
			}
		}
		return msg;
	}
}
