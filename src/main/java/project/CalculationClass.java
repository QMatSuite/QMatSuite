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

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;

import agent.InputAgent;
import agent.InputAgentGeo;
import com.consts.Constants.EnumCalc;
import com.consts.Constants.EnumStep;
import input.ContainerInputString;
import input.QeInput;

public abstract class CalculationClass implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 4624943336997290724L;
	
	protected String calcName;
	protected EnumCalc nameCalc;
	protected HashMap<EnumStep, String> commandList;
	transient protected HashMap<EnumStep, QeInput> inputList;
	protected HashMap<EnumStep, InputAgent> agentList;//direct record of the GUI
	private int geometryIndex;
	
	protected ArrayList<EnumStep> orderList;

	public CalculationClass() {
		commandList = new HashMap<EnumStep, String>();
		reconstructInputList();//contains new inputList
		orderList = new ArrayList<EnumStep>();
		agentList = new HashMap<EnumStep, InputAgent>();
		geometryIndex = 0;
	}
	public String getCalcName() {
		return calcName;
	}
	public void setCalcName(String newName) {
		if(newName!=null && !newName.isEmpty()) {calcName = newName;}
	}
	public int getGeoInd() {
		return geometryIndex;
	}
	public void setGeoInd(int ind) {
		geometryIndex = ind;
	}
	public Boolean existStep(EnumStep es) {
		if (commandList==null || es == null) return false;
		return commandList.containsKey(es);
	}
	public InputAgent getAgent(EnumStep es) {
		if (es==null ) return null;
		return agentList.get(es);
	}
	public void setAgent(EnumStep es,InputAgent ia) {
		if (es==null || ia==null) return;
		agentList.put(es, ia);
	}
	public QeInput getQeInput(EnumStep index) {
		if (index==null || ! inputList.containsKey(index)) return null;
		else return inputList.get(index);
	}
	public EnumCalc getCalcType() {
		return nameCalc;
	}
	protected abstract void reconstructInputList();
	public abstract ArrayList<ContainerInputString> genInputFromAgent(ArrayList<InputAgentGeo> geoList);
}
