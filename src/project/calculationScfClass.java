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
import agent.InputAgentScf;
import input.ContainerInputString;
import input.PwInput;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class calculationScfClass extends calculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 2187936113824732788L;
	public calculationScfClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.SCF;
		
//		commandList.put(EnumStep.GEO,"");
//		orderList.add(EnumStep.GEO);
//		inputList.put(EnumStep.GEO, inp1);
//		agentList.put(EnumStep.GEO,null);
		
		commandList.put(EnumStep.SCF,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.SCF);
		inputList.put(EnumStep.SCF, new PwInput());
		agentList.put(EnumStep.SCF,new InputAgentScf());
	}
	public void genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		inputList.get(EnumStep.SCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.SCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		ContainerInputString inputWrapper= inputList.get(EnumStep.SCF).genInput(EnumStep.SCF);
		
		Alert alert1 = new Alert(AlertType.INFORMATION);
    	alert1.setHeaderText("Input of "+nameCalc);
    	alert1.setContentText(inputWrapper.toString());
    	alert1.showAndWait();
	}
}
