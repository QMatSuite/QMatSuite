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
package main.java.input;

import java.util.Set;

import main.java.agent.InputAgentDos;
import main.java.agent.WrapperBoolean;
import main.java.agent.WrapperDouble;
import main.java.agent.WrapperInteger;
import main.java.agent.WrapperString;
import main.java.com.error.InvalidKeyException;
import main.java.com.error.InvalidTypeException;

public class DosInput extends QeInput{
	
//	public DosInput() {
//		super();
//	}
	@Override
	public String addParameter(InputValue val) {
		return null;
	}
	@Override
	public void print() {
		Set<String> keys = sectionDict.keySet();
        for(String key: keys){
        	sectionDict.get(key).print();
        }
	}
	public Boolean checkKeyExistence(String keySec, String keyPara) {
		if (keySec==null || keyPara ==null) return false;
		if (sectionDict.containsKey(keySec) && sectionDict.get(keySec).containsKey(keyPara)) {
			return true;
		}
		return false;
	}
	public void setValue(String keySec, String keyPara,WrapperDouble para) throws InvalidKeyException, InvalidTypeException {
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in DosInput setValue");}
	}
	public void setValue(String keySec, String keyPara,WrapperInteger para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in DosInput setValue");}
	}
	public void setValue(String keySec, String keyPara,WrapperString para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in DosInput setValue");}
	}
	public void setValue(String keySec, String keyPara,WrapperBoolean para) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValue(para);}
		else {throw new InvalidKeyException("in DosInput setValue");}
	}
	public void setValue(String keySec, String keyPara) throws InvalidKeyException, InvalidTypeException{
		if (checkKeyExistence(keySec, keyPara)) {sectionDict.get(keySec).getValue(keyPara).setValueNow();}
		else {throw new InvalidKeyException("in DosInput setValue");}
	}
	public InputValue getValue(String keySec, String keyPara) throws InvalidKeyException{
		if (checkKeyExistence(keySec, keyPara)) return sectionDict.get(keySec).getValue(keyPara);
		else {throw new InvalidKeyException("in DosInput getValue");}
	}
	@Override
	public void loadAgent(InputAgentDos ia1) {
		// TODO Auto-generated method stub
		
	}
	
}
