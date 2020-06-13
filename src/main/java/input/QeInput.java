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
package input;

import java.util.LinkedHashMap;
import java.util.Set;

import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentNscf;
import agent.InputAgentOpt;
import agent.InputAgentScf;
import agent.WrapperBoolean;
import agent.WrapperDouble;
import agent.WrapperInteger;
import agent.WrapperString;
import com.consts.Constants.EnumStep;
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;

public abstract class QeInput{ 
	
	protected LinkedHashMap<String, InputSection> sectionDict;
	protected String errorMessage;
	
	public QeInput() {
		sectionDict = new LinkedHashMap<String, InputSection> ();
		errorMessage="";
	}
	public void clearErrorMessage() {
		errorMessage="";
	}
	public String getErrorMessage() {
		return errorMessage;
	}
	public abstract String addParameter(InputValue val);
	public abstract void print(); 
	public ContainerInputString genInput(String startingMsg) {
		ContainerInputString ci = new ContainerInputString();
		ci.appendInput(startingMsg);
		Set<String> keys = sectionDict.keySet();
        for(String key: keys){
        	ContainerInputString ciTmp = sectionDict.get(key).toStringWrapper();
        	if (!ciTmp.isEmpty() || sectionDict.get(key).getBoolRequired()) {
        		ci.append(ciTmp);
        	}
        }
		return ci;
	}  
	public ContainerInputString genInput(EnumStep es) {
		ContainerInputString ci = genInput("!"+es.toString()+"\n");
		ci.stepName = es;//necessary!
		ci.appendLog(errorMessage);
		return ci;
	} 
	public abstract void setValue(String keySec, String keyPara) throws InvalidKeyException, InvalidTypeException;//set null
	public abstract void setValue(String keySec, String keyPara,WrapperDouble para) throws InvalidKeyException, InvalidTypeException;
	public abstract void setValue(String keySec, String keyPara,WrapperInteger para) throws InvalidKeyException, InvalidTypeException;
	public abstract void setValue(String keySec, String keyPara,WrapperString para) throws InvalidKeyException, InvalidTypeException;
	public abstract void setValue(String keySec, String keyPara,WrapperBoolean para) throws InvalidKeyException, InvalidTypeException;
	//not abstract method, because no need to define all of them in the inherited class
	public void loadAgent(InputAgentDos ia1) {
		//implement in the subclasses
	}
	public void loadAgent(InputAgentGeo ia1) {
		//implement in the subclasses
	}
	public void loadAgent(InputAgentNscf ia1) {
		//implement in the subclasses
	}
	public void loadAgent(InputAgentOpt ia1) {
		//implement in the subclasses
	}
	public void loadAgent(InputAgentMd ia1) {
		//implement in the subclasses
	}
	public void loadAgent(InputAgentScf ia1) {
		//implement in the subclasses
	} 
}
