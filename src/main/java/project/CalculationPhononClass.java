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
import agent.InputAgentGeo;
import agent.InputAgentPhonon;
import agent.InputAgentScf;
import core.project.CalculationClass;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import input.ContainerInputString;
import input.MatdynInput;
import input.PhInput;
import input.PwInput;
import input.Q2rInput;
import input.QeInput;


public class CalculationPhononClass extends CalculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 8055817090507082088L;

	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    reconstructInputList();
	}
	@Override
	protected void reconstructInputList() {
		inputList = new HashMap<EnumStep, QeInput>();
		inputList.put(EnumStep.SCF,new PwInput());
		inputList.put(EnumStep.PH,new PhInput());
		inputList.put(EnumStep.Q2R,new Q2rInput());
		inputList.put(EnumStep.MATDYN,new MatdynInput());
	}
	public CalculationPhononClass(String cn) {
		super();//contains reconstructInputList()
		this.calcName = cn;
		nameCalc = EnumCalc.PHONON;
		
		agentList.put(EnumStep.SCF,new InputAgentScf());
		agentList.put(EnumStep.PH,new InputAgentPhonon());
		//no Q2R or MATDYN agent! Use the same agent (PH)!
	}
	public ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		ArrayList<ContainerInputString> cis = new ArrayList<ContainerInputString>();
		
		inputList.get(EnumStep.SCF).clearErrorMessage();
		inputList.get(EnumStep.SCF).loadAgent(geoList.get(getGeoInd()));
		inputList.get(EnumStep.SCF).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));
		cis.add(inputList.get(EnumStep.SCF).genInput(EnumStep.SCF));
		
		
		inputList.get(EnumStep.PH).clearErrorMessage();
		inputList.get(EnumStep.PH).loadAgent((InputAgentPhonon)agentList.get(EnumStep.PH));
		cis.add(inputList.get(EnumStep.PH).genInput(EnumStep.PH));
		
		if(((InputAgentPhonon)agentList.get(EnumStep.PH)).ldisp.getValue()) {
			inputList.get(EnumStep.Q2R).clearErrorMessage();
			inputList.get(EnumStep.Q2R).loadAgent((InputAgentPhonon)agentList.get(EnumStep.PH));
			cis.add(inputList.get(EnumStep.Q2R).genInput(EnumStep.Q2R));
			
			inputList.get(EnumStep.MATDYN).clearErrorMessage();
			inputList.get(EnumStep.MATDYN).loadAgent((InputAgentPhonon)agentList.get(EnumStep.PH));
			cis.add(inputList.get(EnumStep.MATDYN).genInput(EnumStep.MATDYN));
		}
		
		return cis;

	}
}
