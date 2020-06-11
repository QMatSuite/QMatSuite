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

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;

import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentScf;
import input.ContainerInputString;
import input.PwInput;
import input.QeInput;

public class CalculationMdClass extends CalculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 138458242473384324L;
	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    inputList = new HashMap<EnumStep, QeInput>();
	    inputList.put(EnumStep.BOMD,new PwInput());
	}
	public CalculationMdClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.BOMD;
		
		commandList.put(EnumStep.SCF,"");
		orderList.add(EnumStep.SCF);
		agentList.put(EnumStep.SCF,new InputAgentScf());
		
		commandList.put(EnumStep.BOMD,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.BOMD);
		inputList.put(EnumStep.BOMD,new PwInput());
		agentList.put(EnumStep.BOMD,new InputAgentMd());
	}
	public ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		ArrayList<ContainerInputString> cis = new ArrayList<ContainerInputString>();
		
		inputList.get(EnumStep.BOMD).clearErrorMessage();
		inputList.get(EnumStep.BOMD).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.BOMD).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		inputList.get(EnumStep.BOMD).loadAgent((InputAgentMd)agentList.get(EnumStep.BOMD));
		cis.add(inputList.get(EnumStep.BOMD).genInput(EnumStep.BOMD));
		
		return cis;
//		Alert alert1 = new Alert(AlertType.INFORMATION);
//    	alert1.setHeaderText("Input of "+nameCalc);
//    	alert1.setContentText(inputWrapper.toString());
//    	alert1.showAndWait();
	}
}
