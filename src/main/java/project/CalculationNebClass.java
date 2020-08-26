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
import agent.InputAgentNeb;
import agent.InputAgentScf;
import core.project.CalculationClass;

import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import input.ContainerInputString;
import input.NebInput;
import input.QeInput;

public class CalculationNebClass extends CalculationClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = -2410616690506734892L;
	
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    reconstructInputList();
	}
	@Override
	protected void reconstructInputList() {
		inputList = new HashMap<EnumStep, QeInput>();
		inputList.put(EnumStep.NEB,new NebInput());
	}
	public CalculationNebClass(String cn) {
		super();
		this.calcName = cn;
		nameCalc = EnumCalc.NEB;
		
		agentList.put(EnumStep.SCF,new InputAgentScf());
		agentList.put(EnumStep.NEB,new InputAgentNeb());
	}
	public boolean checkUsedGeoIndex(int ind) {
		//true is used, false is not used -> ok
		InputAgentNeb iNeb = (InputAgentNeb) agentList.get(EnumStep.NEB);
		return (iNeb.startGeo==ind || iNeb.endGeo==ind);
	}
	public ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList) {
		ArrayList<ContainerInputString> cis = new ArrayList<ContainerInputString>();
		
		inputList.get(EnumStep.NEB).clearErrorMessage();
		((NebInput)inputList.get(EnumStep.NEB)).loadAgent(geoList);//different from others, need to pass the whole list
		inputList.get(EnumStep.NEB).loadAgent((InputAgentNeb)agentList.get(EnumStep.NEB));//load NEB first to load chosen geometries
		inputList.get(EnumStep.NEB).loadAgent((InputAgentScf)agentList.get(EnumStep.SCF));//then load SCF to get corresponding SCF pseudo
		cis.add(inputList.get(EnumStep.NEB).genInput(EnumStep.NEB));
		
		return cis;

	}
}
