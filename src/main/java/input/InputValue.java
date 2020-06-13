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

import java.io.Serializable;

import agent.WrapperBoolean;
import agent.WrapperDouble;
import agent.WrapperInteger;
import agent.WrapperString;
import com.error.InvalidTypeException;

public abstract class InputValue implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 4608210422008015737L;
	
	protected final String nameString;
	protected Boolean boolRequired;
	protected Boolean explicitWrite = false;//cannot set to null

	public InputValue(String ns, Boolean br) {
		boolRequired = br;
		nameString = ns;
	}
	public Boolean isExplicitWrite() {
		return explicitWrite;
	}
	public Boolean isRequired() {
		return boolRequired;
	}
	public void setExplicitWrite(Boolean ew) {
		explicitWrite = ew;
	}
	public void andExplicitWrite(Boolean ew) {
		if(explicitWrite==null) {explicitWrite=ew;return;}
		explicitWrite = (ew && explicitWrite);
	}
	public void print() {
		System.out.println(toString());
	}
	public String toString() {
		return toString(false);
	}
	public abstract String toString(boolean bl);
	//********remove the abstract keyword so that you do not need to implement all in the inherited class!
	public abstract void setValueNow() throws InvalidTypeException;//set to null
	public abstract void setValueNow(Integer valueNow) throws InvalidTypeException;
	public abstract void setValueNow(Double valueNow) throws InvalidTypeException;
	public abstract void setValueNow(String valueNow) throws InvalidTypeException;
	public abstract void setValueNow(Boolean valueNow) throws InvalidTypeException;
	public void setValue(WrapperInteger val) throws InvalidTypeException {
		setValueNow(val.getValue());
		setExplicitWrite(val.isEnabled());
	}
	public void setValue(WrapperDouble val) throws InvalidTypeException {
		setValueNow(val.getValue());
		setExplicitWrite(val.isEnabled());
	}
	public void setValue(WrapperString val) throws InvalidTypeException {
		setValueNow(val.getValue().toString());
		setExplicitWrite(val.isEnabled());
	}
	public void setValue(WrapperBoolean val) throws InvalidTypeException {
		setValueNow(val.getValue());
		setExplicitWrite(val.isEnabled());
	}
	public void setRequiredAndWrite(Boolean bl1, Boolean bl2){
		boolRequired = bl1;
		explicitWrite = bl2;
	}
	
}
