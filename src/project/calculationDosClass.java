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

import java.util.ArrayList;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;

import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentNscf;
import agent.InputAgentScf;
import input.DosInput;
import input.PwInput;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class calculationDosClass extends calculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7797188687240412631L;
	public calculationDosClass() {
		super();
		nameCalc = EnumCalc.DOS;
		
//		PwInput inp1 = new PwInput();
		
//		commandList.put(EnumStep.GEO,"");
//		orderList.add(EnumStep.GEO);
//		inputList.put(EnumStep.GEO,null);
//		agentList.put(EnumStep.GEO,null);
		
		commandList.put(EnumStep.SCF,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.SCF);
		inputList.put(EnumStep.SCF,new PwInput());
		agentList.put(EnumStep.SCF,new InputAgentScf());
		
//		PwInput inp2 = new PwInput();
		
		commandList.put(EnumStep.NSCF,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.NSCF);
		inputList.put(EnumStep.NSCF,new PwInput());
		agentList.put(EnumStep.NSCF,new InputAgentNscf());
		
//		DosInput inp3 = new DosInput();
		
		commandList.put(EnumStep.DOS,"dos.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.DOS);
		inputList.put(EnumStep.DOS,new DosInput());
		agentList.put(EnumStep.DOS,new InputAgentDos());
	}
	public void genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		inputList.get(EnumStep.SCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.SCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		String inputFile= inputList.get(EnumStep.SCF).genInput();
		
		Alert alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setHeaderText("Input 1: SCF ("+"Input of "+nameCalc+")");
    	alert1.setContentText(inputFile);
    	alert1.showAndWait();
		
    	//******not efficient. Maybe should implement clone method in QeInput
    	inputList.get(EnumStep.NSCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.NSCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		inputList.get(EnumStep.NSCF).loadAgent((InputAgentNscf)agentList.get(EnumStep.NSCF));
		inputFile= inputList.get(EnumStep.NSCF).genInput();
		
		alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setHeaderText("Input 2: NSCF ("+"Input of "+nameCalc+")");
    	alert1.setContentText(inputFile);
    	alert1.showAndWait();
    	
		inputList.get(EnumStep.DOS).loadAgent((InputAgentDos) agentList.get(EnumStep.DOS));
		inputFile= inputList.get(EnumStep.DOS).genInput();
		
		alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setHeaderText("Input 3: DOS ("+"Input of "+nameCalc+")");
    	alert1.setContentText(inputFile);
    	alert1.showAndWait();
	}
}
