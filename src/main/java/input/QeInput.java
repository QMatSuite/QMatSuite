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

import agent.InputAgentBands;
import agent.InputAgentDos;
import agent.InputAgentGeo;
import agent.InputAgentMd;
import agent.InputAgentNscf;
import agent.InputAgentOpt;
import agent.InputAgentPhonon;
import agent.InputAgentScf;
import agent.InputAgentTddft;
import agent.WrapperBoolean;
import agent.WrapperDouble;
import agent.WrapperEnum;
import agent.WrapperInteger;
import agent.WrapperString;
import com.consts.Constants.EnumStep;
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;

public abstract class QeInput{ 
	
	protected LinkedHashMap<String, InputSection> sectionDict;
	protected String errorMessage;
	protected final String commandName;
	
	public QeInput(String commandName) {
		this.sectionDict = new LinkedHashMap<String, InputSection> ();
		this.errorMessage="";
		this.commandName=commandName;
	}
	public void clearErrorMessage() {
		errorMessage="";
	}
	public String getErrorMessage() {
		return errorMessage;
	}
	public void print() {
		Set<String> keys = sectionDict.keySet();
        for(String key: keys){
        	sectionDict.get(key).print();
        }
	}
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
        ci.commandName = this.commandName;
		return ci;
	}  
	public ContainerInputString genInput(EnumStep es) {
		ContainerInputString ci = genInput("!"+es.toString()+"\n");
		ci.stepName = es;//necessary!
		ci.appendLog(errorMessage);
		return ci;
	} 
	protected void setValue(String keySec, String keyPara,WrapperDouble para) throws InvalidKeyException, InvalidTypeException {
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara,WrapperDouble para, double mulFactor) throws InvalidKeyException, InvalidTypeException {
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para,mulFactor);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara,WrapperInteger para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara,WrapperString para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara,WrapperBoolean para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara,WrapperEnum para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(new WrapperString(para.getValue().toString(),para.isEnabled()));}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setValue(String keySec, String keyPara) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValueNow();}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setExplicitWrite(String keySec, String keyPara, boolean bl) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setExplicitWrite(bl);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setRequiredAndWrite(String keySec, String keyPara, boolean bl1, boolean bl2) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setRequiredAndWrite(bl1,bl2);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void andExplicitWrite(String keySec, String keyPara, boolean bl) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).andExplicitWrite(bl);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected InputValue getValue(String keySec, String keyPara) throws InvalidKeyException{
		if (checkKeyExistence(keySec, keyPara)) return sectionDict.get(keySec).getValue(keyPara);
		else {throw new InvalidKeyException("in QeInput setValue "+keySec+" "+keyPara);}
	}
	protected void setSectionRequired(String keySec, Boolean bl) throws InvalidKeyException, InvalidTypeException{
		if (keySec!=null && sectionDict.containsKey(keySec) && bl!=null) {sectionDict.get(keySec).setBoolRequired(bl);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec);}
	}
	protected void setSectionOption(String keySec, String st) throws InvalidKeyException, InvalidTypeException{
		if (keySec!=null && sectionDict.containsKey(keySec) && st!=null) {sectionDict.get(keySec).setOptions(st);}
		else {throw new InvalidKeyException("in QeInput setValue "+keySec);}
	}
	protected Boolean checkKeyExistence(String keySec, String keyPara) {
		if (keySec==null || keyPara ==null) return false;
		if (sectionDict.containsKey(keySec) && sectionDict.get(keySec).containsKey(keyPara)) {
			return true;
		}
		return false;
	}
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
	public void loadAgent(InputAgentBands ia1) {
		//implement in the subclasses
	} 
	public void loadAgent(InputAgentTddft ia1) {
		//implement in the subclasses
	} 
	public void loadAgent(InputAgentPhonon ia1) {
		//implement in the subclasses
	}
}
