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
package agent;

public class WrapperString extends WrapperClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 6353893107280121267L;
	private String value;
	final private String defaultValue;
	
	public WrapperString(String val) {
		defaultValue = val;
		value = val;
		enabled = false;
	}
	public WrapperString(String val,Boolean bl) {
		defaultValue = val;
		value = val;
		enabled = bl;
	}
	public String getValue() {
		return value;
	}
	public void setValue(String val) {
		value = val;
	}
	public Boolean equals(String vl) {
		return java.util.Objects.equals(vl, value);
	}
	@Override
	public Boolean isNull() {
		return value==null || value.isEmpty();
	}
	public String resetDefault() {
		value = defaultValue;
		return defaultValue;
	}
	@Override
	public Boolean isDefaultNull() {
		return defaultValue==null;
	}
}