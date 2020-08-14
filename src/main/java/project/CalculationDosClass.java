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
package project;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;

import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentNscf;
import agent.InputAgentScf;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import input.ContainerInputString;
import input.DosInput;
import input.PwInput;
import input.QeInput;

public class CalculationDosClass extends CalculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7797188687240412631L;
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization, necessary!
	    in.defaultReadObject();
	    reconstructInputList();
	}
	@Override
	protected void reconstructInputList() {
		inputList = new HashMap<EnumStep, QeInput>();
	    inputList.put(EnumStep.SCF, new PwInput());
	    inputList.put(EnumStep.NSCF,new PwInput());
	    inputList.put(EnumStep.DOS,new DosInput());
	}
	public CalculationDosClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.DOS;
		
		agentList.put(EnumStep.SCF,new InputAgentScf());	
		agentList.put(EnumStep.NSCF,new InputAgentNscf());
		agentList.put(EnumStep.DOS,new InputAgentDos());
	}
	
	public ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		ArrayList<ContainerInputString> cis = new ArrayList<ContainerInputString>();
		
		inputList.get(EnumStep.SCF).clearErrorMessage();
		inputList.get(EnumStep.SCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.SCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		cis.add(inputList.get(EnumStep.SCF).genInput(EnumStep.SCF));
		
//		Alert alert1 = new Alert(AlertType.INFORMATION);
//    	alert1.setHeaderText("Input 1: SCF ("+"Input of "+nameCalc+")");
//    	alert1.setContentText(inputWrapper.toString());
//    	alert1.showAndWait();
		
    	//******not efficient. Maybe should implement clone method in QeInput
    	inputList.get(EnumStep.NSCF).clearErrorMessage();
    	inputList.get(EnumStep.NSCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.NSCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		inputList.get(EnumStep.NSCF).loadAgent((InputAgentNscf)agentList.get(EnumStep.NSCF));
		cis.add(inputList.get(EnumStep.NSCF).genInput(EnumStep.NSCF));
		
//		alert1 = new Alert(AlertType.INFORMATION);
//    	alert1.setHeaderText("Input 2: NSCF ("+"Input of "+nameCalc+")");
//    	alert1.setContentText(inputWrapper.toString());
//    	alert1.showAndWait();
    	
    	inputList.get(EnumStep.DOS).clearErrorMessage();
		inputList.get(EnumStep.DOS).loadAgent((InputAgentDos) agentList.get(EnumStep.DOS));
		cis.add(inputList.get(EnumStep.DOS).genInput(EnumStep.DOS));
		
		return cis;
		
//		alert1 = new Alert(AlertType.INFORMATION);
//    	alert1.setHeaderText("Input 3: DOS ("+"Input of "+nameCalc+")");
//    	alert1.setContentText(inputWrapper.toString());
//    	alert1.showAndWait();
	}
}
