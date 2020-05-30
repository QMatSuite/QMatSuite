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

import agent.InputAgentGeo;
import agent.InputAgentOpt;
import agent.InputAgentScf;
import input.ContainerInputString;
import input.PwInput;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class calculationOptClass extends calculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 138458242473384324L;
	public calculationOptClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.OPT;
		
//		commandList.put(EnumStep.GEO,"");
//		orderList.add(EnumStep.GEO);
//		inputList.put(EnumStep.GEO,null);
//		agentList.put(EnumStep.GEO,null);
		
		commandList.put(EnumStep.SCF,"");
		orderList.add(EnumStep.SCF);
		inputList.put(EnumStep.SCF,null);
		agentList.put(EnumStep.SCF,new InputAgentScf());
		
		commandList.put(EnumStep.OPT,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.OPT);
		inputList.put(EnumStep.OPT,new PwInput());
		agentList.put(EnumStep.OPT,new InputAgentOpt());
	}
	public void genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		inputList.get(EnumStep.OPT).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.OPT).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		inputList.get(EnumStep.OPT).loadAgent((InputAgentOpt)agentList.get(EnumStep.OPT));
		ContainerInputString inputWrapper= inputList.get(EnumStep.OPT).genInput(EnumStep.OPT);
		
		Alert alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setHeaderText("Input of "+nameCalc);
    	alert1.setContentText(inputWrapper.toString());
    	alert1.showAndWait();
	}
}
