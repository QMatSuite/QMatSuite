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

import agent.InputAgentBands;
import agent.InputAgentGeo;
import agent.InputAgentScf;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import input.ContainerInputString;
import input.PwInput;
import input.QeInput;

public class CalculationBandsClass extends CalculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 138458242473384324L;
	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    inputList = new HashMap<EnumStep, QeInput>();
	    inputList.put(EnumStep.BANDS,new PwInput());
	}
	public CalculationBandsClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.BANDS;
		
		commandList.put(EnumStep.SCF,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.SCF);
		inputList.put(EnumStep.SCF,new PwInput());
		agentList.put(EnumStep.SCF,new InputAgentScf());
		
		commandList.put(EnumStep.BANDS,"pw.exe < espresso.in > espresso.out");
		orderList.add(EnumStep.BANDS);
		inputList.put(EnumStep.BANDS,new PwInput());
		agentList.put(EnumStep.BANDS,new InputAgentBands());
	}
	public ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		ArrayList<ContainerInputString> cis = new ArrayList<ContainerInputString>();
		
		inputList.get(EnumStep.SCF).clearErrorMessage();
		inputList.get(EnumStep.SCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.SCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		cis.add(inputList.get(EnumStep.SCF).genInput(EnumStep.SCF));
		
		
		inputList.get(EnumStep.BANDS).clearErrorMessage();
		inputList.get(EnumStep.BANDS).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.BANDS).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		inputList.get(EnumStep.BANDS).loadAgent((InputAgentBands)agentList.get(EnumStep.BANDS));
		cis.add(inputList.get(EnumStep.BANDS).genInput(EnumStep.BANDS));
		
		return cis;
//		Alert alert1 = new Alert(AlertType.INFORMATION);
//    	alert1.setHeaderText("Input of "+nameCalc);
//    	alert1.setContentText(inputWrapper.toString());
//    	alert1.showAndWait();
	}
}
